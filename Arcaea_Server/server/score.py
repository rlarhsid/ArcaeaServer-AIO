from random import randint
from time import time

from flask import Blueprint, request

from core.constant import Constant
from core.course import CoursePlay
from core.error import InputError
from core.rank import RankList
from core.score import UserPlay
from core.sql import Connect
from core.user import UserOnline

from .auth import auth_required
from .func import arc_try, success_return

bp = Blueprint('score', __name__, url_prefix='/score')


@bp.route('/token', methods=['GET'])  # 成绩上传所需的token，显然我不想验证
def score_token():
    return success_return({'token': '1145141919810'})


@bp.route('/token/world', methods=['GET'])  # 世界模式成绩上传所需的token
@auth_required(request)
@arc_try
def score_token_world(user_id):

    d = request.args.get

    stamina_multiply = d('stamina_multiply', 1, type=int)
    fragment_multiply = d('fragment_multiply', 100, type=int)
    prog_boost_multiply = d('prog_boost_multiply', 0, type=int)
    beyond_boost_gauge_use = d('beyond_boost_gauge_use', 0, type=int)
    skill_cytusii_flag = None
    skill_chinatsu_flag = None
    skill_id = d('skill_id')

    if (skill_id == 'skill_ilith_ivy' or skill_id == 'skill_hikari_vanessa') and d('is_skill_sealed') == 'false':
        # 处理 ivy 技能或者 vanessa 技能
        # TODO: 需要重构整个 user_play，世界模式 / 课题模式，所以现在临时 work 一下
        skill_cytusii_flag = ''.join([str(randint(0, 2)) for _ in range(5)])

    if skill_id == 'skill_chinatsu' and d('is_skill_sealed') == 'false':
        skill_chinatsu_flag = ''.join([str(randint(0, 2)) for _ in range(7)])
    skill_flag = skill_cytusii_flag or skill_chinatsu_flag

    with Connect() as c:
        x = UserPlay(c, UserOnline(c, user_id))
        x.song.set_chart(d('song_id'), d('difficulty', type=int))
        x.set_play_state_for_world(
            stamina_multiply, fragment_multiply, prog_boost_multiply, beyond_boost_gauge_use, skill_cytusii_flag, skill_chinatsu_flag)

        r = {
            "stamina": x.user.stamina.stamina,
            "max_stamina_ts": x.user.stamina.max_stamina_ts,
            "token": x.song_token,
            "play_parameters": {},
            "beyond_boost_gauge": x.user.beyond_boost_gauge
        }
        if skill_flag and skill_id:
            r['play_parameters'] = {
                skill_id: list(
                    map(lambda x: Constant.WORLD_VALUE_NAME_ENUM[int(x)], skill_flag)),
            }
        if x.invasion_flag == 1:
            r['play_parameters']['invasion_start'] = True
        elif x.invasion_flag == 2:
            r['play_parameters']['invasion_hard'] = True
        
        return success_return(r)


@bp.route('/token/course', methods=['GET'])  # 课题模式成绩上传所需的token
@auth_required(request)
@arc_try
def score_token_course(user_id):
    with Connect() as c:
        use_course_skip_purchase = request.args.get(
            'use_course_skip_purchase', 'false') == 'true'

        user = UserOnline(c, user_id)
        user_play = UserPlay(c, user)
        user_play.song_token = request.args.get('previous_token', None)
        user_play.get_play_state()

        status = 'created'
        if user_play.course_play_state == -1:
            # 没有token，课题模式刚开始
            course_play = CoursePlay(c, user, user_play)
            course_play.course_id = request.args['course_id']
            user_play.course_play = course_play
            user_play.set_play_state_for_course(
                use_course_skip_purchase)
        elif 0 <= user_play.course_play_state <= 3:
            # 验证token
            user_play.update_token_for_course()
        else:
            # 课题模式已经结束
            user_play.clear_play_state()
            user.select_user_about_stamina()
            status = 'cleared' if user_play.course_play_state == 4 else 'failed'

        return success_return({
            "stamina": user.stamina.stamina,
            "max_stamina_ts": user.stamina.max_stamina_ts,
            "token": user_play.song_token,
            'status': status
        })


@bp.route('/song', methods=['POST'])  # 成绩上传
@auth_required(request)
@arc_try
def song_score_post(user_id):
    with Connect() as c:
        x = UserPlay(c, UserOnline(c, user_id))
        x.nell_toggle = request.args.get("nell_toggle",type=bool)
        x.song_token = request.form['song_token']
        x.song_hash = request.form['song_hash']
        x.song.set_chart(
            request.form['song_id'], request.form['difficulty'])
        x.set_score(request.form['score'], request.form['shiny_perfect_count'], request.form['perfect_count'], request.form['near_count'],
                    request.form['miss_count'], request.form['health'], request.form['modifier'], int(time() * 1000), request.form['clear_type'])
        x.beyond_gauge = int(request.form['beyond_gauge'])
        x.submission_hash = request.form['submission_hash']
        if 'combo_interval_bonus' in request.form:
            x.combo_interval_bonus = int(request.form['combo_interval_bonus'])
        if 'hp_interval_bonus' in request.form:
            x.hp_interval_bonus = int(request.form['hp_interval_bonus'])
        # visible_map_count
        if 'fever_bonus' in request.form:
            x.fever_bonus = int(request.form['fever_bonus'])
        x.highest_health = request.form.get("highest_health", type=int)
        x.lowest_health = request.form.get("lowest_health", type=int)
        if not x.is_valid:
            raise InputError('Invalid score.', 107)
        x.upload_score()
        # room_code???
        return success_return(x.to_dict())


@bp.route('/song', methods=['GET'])  # TOP20
@auth_required(request)
@arc_try
def song_score_top(user_id):
    with Connect() as c:
        rank_list = RankList(c)
        rank_list.song.set_chart(request.args.get(
            'song_id'), request.args.get('difficulty'))
        rank_list.select_top()
        return success_return(rank_list.to_dict_list())


@bp.route('/song/me', methods=['GET'])  # 我的排名，默认最多20
@auth_required(request)
@arc_try
def song_score_me(user_id):
    with Connect() as c:
        rank_list = RankList(c)
        rank_list.song.set_chart(request.args.get(
            'song_id'), request.args.get('difficulty'))
        rank_list.select_me(UserOnline(c, user_id))
        return success_return(rank_list.to_dict_list())


@bp.route('/song/friend', methods=['GET'])  # 好友排名，默认最多50
@auth_required(request)
@arc_try
def song_score_friend(user_id):
    with Connect() as c:
        rank_list = RankList(c)
        rank_list.song.set_chart(request.args.get(
            'song_id'), request.args.get('difficulty'))
        rank_list.select_friend(UserOnline(c, user_id))
        return success_return(rank_list.to_dict_list())
