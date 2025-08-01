import os
import discord
from discord import app_commands
import requests
import sqlite3
import json
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SERVER_URL = os.getenv("SERVER_URL")
API_TOKEN = os.getenv("API_TOKEN")
DB_PATH = os.getenv("DB_PATH")
SONGLIST_PATH = os.getenv("SONGLIST_PATH")
BACKGROUND_PATH = os.getenv("BACKGROUND_PATH")
FONT_PATH = os.getenv("FONT_PATH")
JACKET_PATH = os.getenv("JACKET_PATH")

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


def load_songlist():
    with open(SONGLIST_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def get_user_id(name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for table in ["user"]:
        cursor.execute(f"SELECT user_id FROM {table} WHERE name = ?", (name,))
        result = cursor.fetchone()
        if result:
            conn.close()
            return result[0]
    conn.close()
    return None


def get_album_cover(song_id):
    if not JACKET_PATH:
        return None

    for folder in os.listdir(JACKET_PATH):
        normalized = folder
        if folder.lower().startswith("dl_"):
            normalized = folder[3:]

        if normalized.lower() == song_id.lower():
            for fname in ["1080_base.jpg", "base.jpg"]:
                full_path = os.path.join(JACKET_PATH, folder, fname)
                if os.path.exists(full_path):
                    return full_path

    return None


def get_rating(songlist, song_id, difficulty):
    for song in songlist.get("songs", []):
        if song["id"] == song_id:
            for diff in song.get("difficulties", []):
                if diff.get("ratingClass") == difficulty:
                    rating = diff.get("rating", "N/A")
                    return (
                        f"{rating}+" if diff.get("ratingPlus", False) else f"{rating}"
                    )
    return "N/A"


def get_difficulty_v2_color(difficulty_v2):
    difficulty_colors = {
        0: os.getenv("RATING_CLASS_0_COLOR", "10, 130, 190"),
        1: os.getenv("RATING_CLASS_1_COLOR", "100, 140, 60"),
        2: os.getenv("RATING_CLASS_2_COLOR", "80, 25, 75"),
        3: os.getenv("RATING_CLASS_3_COLOR", "130, 35, 40"),
        4: os.getenv("RATING_CLASS_4_COLOR", "161, 132, 181"),
    }
    color_str = difficulty_colors.get(difficulty_v2, "255,255,255")
    return tuple(map(int, color_str.split(",")))


def fetch_user_b30(user_id, songlist):
    api_url = f"{SERVER_URL}/api/v1/users/{user_id}/b30"
    headers = {"Token": API_TOKEN}
    response = requests.get(api_url, headers=headers)
    data = response.json().get("data", {}).get("data", [])
    formatted_data = []
    for item in data:
        song_id = item.get("song_id", "Unknown")
        difficulty = item.get("difficulty", -1)
        difficulty_v2 = item.get("difficulty")
        score = item.get("score", "N/A")
        rating = get_rating(songlist, song_id, difficulty)
        real_rating = round(item.get("rating", 0), 2)
        formatted_data.append(
            {
                "song_id": song_id,
                "song_name": item["song_name"],
                "score": score,
                "rating": rating,
                "real_rating": real_rating,
                "difficulty_v2": difficulty_v2,
            }
        )
    return formatted_data


def create_b30_image(data, username):
    columns = 5
    spacing = 12
    album_size = 320
    box_width = album_size
    box_height = album_size + 120
    outer_padding = 60
    level_padding = (12, 6)
    font_color = "black"

    rows = (len(data) + columns - 1) // columns
    image_width = outer_padding * 2 + columns * (box_width + spacing)
    image_height = outer_padding * 2 + rows * (box_height + spacing)

    background = Image.open(BACKGROUND_PATH).resize((image_width, image_height))
    image = background.copy()
    draw = ImageDraw.Draw(image)

    try:
        font_large = ImageFont.truetype(FONT_PATH, 26)
        font_small = ImageFont.truetype(FONT_PATH, 20)
        font_overlay = ImageFont.truetype(FONT_PATH, 32)
    except:
        font_large = ImageFont.truetype("arial.ttf", 26)
        font_small = ImageFont.truetype("arial.ttf", 20)
        font_overlay = ImageFont.truetype("arial.ttf", 32)

    for idx, entry in enumerate(data):
        col = idx % columns
        row = idx // columns
        x = outer_padding + col * (box_width + spacing)
        y = outer_padding + row * (box_height + spacing)

        draw.rectangle([x, y, x + box_width, y + box_height], fill=(255, 255, 255))

        album_cover = get_album_cover(entry["song_id"])

        cover = Image.open(album_cover).resize(
            (album_size + 1, album_size), Image.LANCZOS
        )
        image.paste(cover, (x, y))

        level_text = entry["rating"]
        bbox = font_overlay.getbbox(level_text)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1] + 12

        level_padding = (14, 10)
        level_box_w = text_w + level_padding[0] * 2
        level_box_h = text_h + level_padding[1] * 2

        level_x = x + album_size - level_box_w
        level_y = y
        color = get_difficulty_v2_color(entry.get("difficulty_v2", 1))

        draw.rectangle(
            [level_x, level_y, level_x + level_box_w, level_y + level_box_h], fill=color
        )

        text_x = level_x + (level_box_w - text_w) // 2
        text_y = level_y + (level_box_h - text_h) // 2
        draw.text((text_x, text_y), level_text, fill="white", font=font_overlay)

        song_name = entry["song_name"]
        if len(song_name) > 11:
            song_name = song_name[:11] + "..."

        text_base_x = x + spacing
        text_base_y = y + album_size + spacing
        draw.text(
            (text_base_x, text_base_y),
            f"#{idx+1} {song_name}",
            fill=font_color,
            font=font_large,
        )
        draw.text(
            (text_base_x, text_base_y + 45),
            f"Score: {entry['score']}",
            fill=font_color,
            font=font_small,
        )
        draw.text(
            (text_base_x, text_base_y + 70),
            f"Rating: {entry['real_rating']}",
            fill=font_color,
            font=font_small,
        )

    image_path = f"{username}_b30.png"
    image.save(image_path)
    return image_path


@tree.command(name="b30", description="Fetch user B30 data.")
async def b30(interaction: discord.Interaction, username: str):
    await interaction.response.defer()
    songlist = load_songlist()
    user_id = get_user_id(username)
    if not user_id:
        await interaction.followup.send(f"User '{username}' not found.")
        return
    data = fetch_user_b30(user_id, songlist)
    image_path = create_b30_image(data, username)
    await interaction.followup.send(file=discord.File(image_path))
    os.remove(image_path)


@bot.event
async def on_ready():
    await tree.sync()
    print(f"{bot.user} is ready!")


bot.run(TOKEN)
