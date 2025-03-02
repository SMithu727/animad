from app_factory import create_app
from extensions import db
from models import Anime, Episode, EpisodeEmbed
import json
import requests

app = create_app()
app.app_context().push()  # Ensure database operations work within the app context

# Define the MAL code for the anime you want to update.
corrupt_mal_code = '42941'  # Replace with the actual MAL code

# Load the JSON file containing your full anime list with episode data.
with open('anime_list.json', encoding='utf-8') as f:
    anime_list = json.load(f)

# Fetch the anime from the database using its MAL code.
anime = Anime.query.filter_by(mal_id=corrupt_mal_code).first()  # Use mal_id instead of mal_code
if not anime:
    print(f"Anime with MAL ID {corrupt_mal_code} not found in the database. Exiting.")
    exit()

print(f"\nUpdating anime '{anime.title}' (MAL ID: {corrupt_mal_code}) from MAL API...")

# Fetch updated data from the MAL API.
response = requests.get(f"https://api.jikan.moe/v4/anime/{corrupt_mal_code}")
if response.status_code == 200:
    api_data = response.json().get("data", {})
    if not api_data:
        print(f"  No data found from MAL for ID {corrupt_mal_code}. Exiting.")
        exit()

    # Update the anime fields using the API response.
    anime.title = api_data.get("title") or anime.title
    anime.rating = api_data.get("rating")
    anime.episode_count = api_data.get("episodes") or 0
    anime.type = api_data.get("type")
    anime.duration = api_data.get("duration")
    anime.description = api_data.get("synopsis")
    anime.japanese_title = api_data.get("title_japanese")
    anime.synonyms = ", ".join(api_data.get("title_synonyms") or [])
    anime.aired = api_data.get("aired", {}).get("string")
    anime.premiered = api_data.get("season") or ""
    anime.status = api_data.get("status")
    anime.mal_score = api_data.get("score") or 0.0
    anime.genres = ", ".join([genre.get("name") for genre in api_data.get("genres", [])])
    anime.studios = ", ".join([studio.get("name") for studio in api_data.get("studios", [])])
    anime.producers = ", ".join([producer.get("name") for producer in api_data.get("producers", [])])
    anime.poster_image = api_data.get("images", {}).get("jpg", {}).get("large_image_url")
    anime.portrait_image = (
        api_data.get("trailer", {}).get("images", {}).get("maximum_image_url") or
        api_data.get("images", {}).get("jpg", {}).get("large_image_url")
    )
    anime.mal_id = corrupt_mal_code  # Ensure MAL ID is set

    db.session.commit()
    print(f"  Anime '{anime.title}' updated with MAL info.")
else:
    print(f"  Error fetching MAL data for ID {corrupt_mal_code} (status: {response.status_code}). Exiting.")
    exit()

# Find the JSON entry for this anime using its MAL ID.
anime_entry = next((entry for entry in anime_list if entry.get("mal_id") == corrupt_mal_code), None)  # Use mal_id instead of mal_code
if not anime_entry:
    print(f"  No JSON entry found for anime '{anime.title}' (MAL ID: {corrupt_mal_code}). Exiting.")
    exit()

episodes_field = anime_entry.get("episodes")
if not episodes_field or (isinstance(episodes_field, list) and len(episodes_field) == 1 and episodes_field[0] == "No episode found"):
    print(f"  No valid episodes found in JSON for anime '{anime.title}'. Exiting.")
    exit()

print(f"  Updating episodes for anime '{anime.title}'.")

# Remove existing episodes and their associated embeds for this anime.
existing_episodes = Episode.query.filter_by(anime_id=anime.id).all()
for ep in existing_episodes:
    EpisodeEmbed.query.filter_by(episode_id=ep.id).delete()
    db.session.delete(ep)
db.session.commit()
print(f"  Removed {len(existing_episodes)} existing episodes for '{anime.title}'.")

# Re-add episodes from the JSON data.
for ep_data in episodes_field:
    # Ensure the episode data is a dictionary.
    if not isinstance(ep_data, dict):
        print(f"    Skipping invalid episode data for anime '{anime.title}'.")
        continue

    embed_srcs = ep_data.get("embed_srcs")
    # Skip if embed sources indicate no links.
    if isinstance(embed_srcs, list) and len(embed_srcs) == 1 and embed_srcs[0] == "No embed links":
        print(f"    Skipping episode {ep_data.get('episode')} for '{anime.title}' due to no embed links.")
        continue

    episode_number = ep_data.get("episode")
    episode_url = ep_data.get("episode_url")
    episode = Episode(
        anime_id=anime.id,
        episode_number=episode_number,
        episode_url=episode_url
    )
    db.session.add(episode)
    db.session.commit()  # Commit to generate an ID for the episode.
    print(f"    Added episode {episode_number} for '{anime.title}'.")

    # Process and add embed sources for this episode.
    for embed in embed_srcs:
        if not isinstance(embed, dict):
            print(f"      Skipping invalid embed data for episode {episode_number} in '{anime.title}'.")
            continue

        server = embed.get("server")
        link = embed.get("link")
        if not server or not link:
            print(f"      Skipping embed for episode {episode_number} in '{anime.title}' due to missing server/link.")
            continue

        embed_obj = EpisodeEmbed(
            episode_id=episode.id,
            server=server,
            link=link
        )
        db.session.add(embed_obj)
        print(f"      Added embed '{server}' for episode {episode_number}.")

    db.session.commit()

print("\nUpdate completed for the selected anime.")