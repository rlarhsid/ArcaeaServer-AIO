import os
import time
import re
import json
from dotenv import load_dotenv
from discord_webhook import DiscordWebhook, DiscordEmbed

load_dotenv()

LOG_FILE_PATH = os.getenv("LOG_FILE_PATH")
SONGLIST_PATH = os.getenv("SONGLIST_PATH")
JACKET_PATH = os.getenv("JACKET_PATH")
MESSAGE_COLOR = os.getenv("MESSAGE_COLOR")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


def get_song_difficulty(difficulty):
    song_difficulties = {
        "0": "Past",
        "1": "Present",
        "2": "Future",
        "3": "Beyond",
        "4": "Eternal",
    }
    return song_difficulties.get(str(difficulty), "Unknown")


def load_songlist():
    if SONGLIST_PATH and os.path.exists(SONGLIST_PATH):
        try:
            with open(SONGLIST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("Error: Invalid JSON in songlist!")
    else:
        print("Error: Songlist file not found! (Did you set the path correctly?)")
    return {"songs": []}


def get_song_title(song_id):
    songlist = load_songlist()
    songs = songlist.get("songs", [])
    song_id = str(song_id)
    for song in songs:
        if isinstance(song, dict):
            if str(song.get("idx", song.get("id", ""))) == song_id:
                return song.get("title_localized", {}).get("en", f"Song {song_id}\n")
    return f"{song_id}\n"


def get_song_jacket(song_id):
    if not JACKET_PATH or not os.path.exists(JACKET_PATH):
        print("Error: JACKET_PATH not found! (Did you set the path correctly?)")
        return None

    songlist = load_songlist()
    songs = songlist.get("songs", [])
    song_id = str(song_id)
    target_id = None

    for song in songs:
        if isinstance(song, dict) and str(song.get("idx")) == song_id:
            target_id = song.get("id")
            break

    if not target_id:
        print(f"Error: No matching idx / song_id found!")
        return None

    matched_folder = None
    for folder in os.listdir(JACKET_PATH):
        if target_id in folder:
            matched_folder = os.path.join(JACKET_PATH, folder)
            break

    if not matched_folder or not os.path.isdir(matched_folder):
        print(f"Error: No folder found!")
        return None

    jacket_file = os.path.join(matched_folder, "1080_base.jpg")
    if not os.path.exists(jacket_file):
        jacket_file = os.path.join(matched_folder, "base.jpg")
        if not os.path.exists(jacket_file):
            print(f"Error: No jacket image (1080_base.jpg / base.png) found!")
            return None

    return jacket_file


def send_discord_notification(title, description, color=MESSAGE_COLOR, song_id=None):
    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL)

    embed = DiscordEmbed(title=title, description=description, color=color)

    if song_id:
        jacket_file = get_song_jacket(song_id)
        if jacket_file and os.path.exists(jacket_file):
            with open(jacket_file, "rb") as f:
                webhook.add_file(file=f.read(), filename="1080_base.jpg")

            embed.set_image(url=f"attachment://1080_base.jpg")

    webhook.add_embed(embed)

    webhook.execute()


def parse_log_line(line):
    patterns = {
        "create_room": r"Create room `(?P<room_code>\w+)` by player `(?P<player_name>\w+)`",
        "join_room": r"Player `(?P<player_name>\w+)` joins room `(?P<room_code>\w+)`",
        "host_change": r"Player `(?P<player_name>\w+)` becomes the host of room `(?P<room_code>\w+)`",
        "vote_song": r"Player `(?P<player_name>\w+)` votes for song `(?P<song_id>\d+)`",
        "selected_song": r"Room `(?P<room_code>\w+)` selected song `(?P<song_id>\d+)`",
        "start_song": r"Room `(?P<room_code>\w+)` starts playing song",  # `(?P<song_id>\d+)`
        "random_selected_song": r"Room `(?P<room_code>\w+)` randomly selected song `(?P<song_id>\d+)`",
        "finish_song": r"Room `(?P<room_code>\w+)` finishes song",  # `(?P<song_id>\d+)`
        "score": (
            r"Player `(?P<player_name>\w+)` - "
            r"Score: (?P<score>\d+), Cleartype: (?P<cleartype>\d+), Difficulty: (?P<difficulty>\d+), "
            r"Timer: (?P<timer>\d+), Best Score Flag: (?P<best_score_flag>\d+), "
            r"Best Player Flag: (?P<best_player_flag>\d+), Shiny Perfect: (?P<shiny_perfect>\d+), "
            r"Perfect: (?P<perfect>\d+), Near: (?P<near>\d+), Miss: (?P<miss>\d+), "
            r"Early: (?P<early>\d+), Late: (?P<late>\d+), Healthy: (?P<healthy>\d+)"
        ),
        "leave_room": r"Player `(?P<player_name>\w+)` leaves room `(?P<room_code>\w+)`",
        "clean_room": r"Clean room `(?P<room_code>\w+)`",
    }
    for event, pattern in patterns.items():
        match = re.search(pattern, line)
        if match:
            data = match.groupdict()
            data["event"] = event
            return data
    return None


def monitor_log_file(file_path):
    with open(file_path, "r") as file:
        file.seek(0, os.SEEK_END)
        print(f"Monitoring {file_path}...")
        while True:
            line = file.readline()
            if line:
                log_info = parse_log_line(line.strip())
                if log_info:
                    event = log_info["event"]
                    title = ""
                    description = ""
                    if event == "create_room":
                        title = "🎉 Room Created"
                        description = (
                            f"**🧑‍💻 Player:** {log_info['player_name']}\n"
                            f"**🏠 Room Code:** {log_info['room_code']}"
                        )
                    elif event == "join_room":
                        title = "🙋 Player Joined"
                        description = (
                            f"**🧑‍💻 Player:** {log_info['player_name']}\n"
                            f"**🏠 Room Code:** {log_info['room_code']}"
                        )
                    elif event == "host_change":
                        title = "🤝 Host Changed"
                        description = (
                            f"**🧑‍💻 Player:** {log_info['player_name']}\n"
                            f"**🏠 Room Code:** {log_info['room_code']}"
                        )
                    elif event == "vote_song":
                        title = "🎵 Song Voted"
                        song_title = get_song_title(log_info["song_id"])
                        description = (
                            f"**🧑‍💻 Player:** {log_info['player_name']}\n"
                            f"**🎶 Song:** {song_title}"
                        )
                    elif event == "selected_song":
                        title = "👏 Song Selected"
                        song_title = get_song_title(log_info["song_id"])
                        description = (
                            f"**🎶 Song:** {song_title}\n"
                            f"**🏠 Room Code:** {log_info['room_code']}"
                        )
                    elif event == "random_selected_song":
                        title = "👏 Song Selected"
                        song_title = get_song_title(log_info["song_id"])
                        description = (
                            f"🎲 Random song selected!\n"
                            f"**🎶 Song:** {song_title}\n"
                            f"**🏠 Room Code:** {log_info['room_code']}"
                        )
                    elif event == "start_song":
                        title = "🏁 Game Started"
                        description = f"**🏠 Room Code:** {log_info['room_code']}"
                    elif event == "finish_song":
                        title = "🏁 Game Finished"
                        description = f"**🏠 Room Code:** {log_info['room_code']}"
                    elif event == "score":
                        title = "🏆 Player Score"
                        song_difficulty = get_song_difficulty(log_info["difficulty"])
                        description = (
                            f"**🧑‍💻 Player:** {log_info['player_name']}\n"
                            f"**✨ Score:** {log_info['score']}\n"
                            f"**🎮 Difficulty:** {song_difficulty}\n\n"
                            f"**🎯Judgement**\n"
                            f"**Pure:** {log_info['perfect']} (+{log_info['shiny_perfect']})\n"
                            f"**Near:** {log_info['near']} (Early: {log_info['early']}, Late: {log_info['late']})\n"
                            f"**Lost:** {log_info['miss']}"
                        )
                    elif event == "leave_room":
                        title = "🚪 Player Left"
                        description = (
                            f"**🧑‍💻 Player:** {log_info['player_name']}\n"
                            f"**🏠 Room Code:** {log_info['room_code']}"
                        )
                    elif event == "clean_room":
                        title = "🧹 Room Closed"
                        description = (
                            f"**👀** As nobody remains, the room has been closed.\n"
                            f"**🏠 Room Code:** {log_info['room_code']}"
                        )
                    else:
                        title = "ℹ️ Linkplay Info"
                        description = line.strip()

                    if title and description:
                        send_discord_notification(
                            title, description, song_id=log_info.get("song_id")
                        )

            time.sleep(0.8)


if __name__ == "__main__":
    if not os.path.exists(LOG_FILE_PATH):
        print(f"Error: Log file {LOG_FILE_PATH} does not exist!")
    else:
        monitor_log_file(LOG_FILE_PATH)
