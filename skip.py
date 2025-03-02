from app_factory import create_app
from extensions import db
from models import Anime, Episode, EpisodeEmbed
import json
import requests

app = create_app()
app.app_context().push()  # Push the application context so that database operations work

# Lists to hold data for skipped anime and episodes
skipped_animes = []
skipped_episodes = []

# Load the JSON file
with open('anime_list.json', encoding='utf-8') as f:
    data = json.load(f)

total_anime = len(data)
print(f"Starting import of {total_anime} anime entries.")

# Process each anime entry with an index for progress tracking.
for index, anime_entry in enumerate(data, start=1):
    anime_name = anime_entry.get("anime_name")
    mal_code = anime_entry.get("mal_code")
    episodes_field = anime_entry.get("episodes")
    
    # Convert mal_code to an integer (if provided)
    mal_id = int(mal_code) if mal_code and mal_code.isdigit() else None

    print(f"\n[{index}/{total_anime}] Processing anime: '{anime_name}' (MAL ID: {mal_id})")

    # Stop processing if we reach the specified anime.
    if mal_code == "43007":
        print("Reached 'Osananajimi ga Zettai ni Makenai Love Comedy'. Stopping processing.")
        break

    # If episodes is empty or indicates no episodes, skip this anime.
    if not episodes_field or (isinstance(episodes_field, list) and len(episodes_field) == 1 and episodes_field[0] == "No episode found"):
        print(f"Skipping anime '{anime_name}' because no episodes were found.")
        skipped_animes.append(anime_entry)
        continue

    # Try to find the anime in the database using the new mal_id field.
    anime = None
    if mal_id:
        anime = Anime.query.filter_by(mal_id=mal_id).first()

    # If not found, try fetching from the MAL API (if mal_id exists)
    if not anime:
        if mal_id:
            print(f"Fetching MAL data for '{anime_name}' with MAL ID {mal_id}...")
            response = requests.get(f"https://api.jikan.moe/v4/anime/{mal_id}")
            if response.status_code == 200:
                api_data = response.json().get("data", {})
                if not api_data:
                    print(f"No MAL data found for ID {mal_id}. Skipping anime '{anime_name}'.")
                    skipped_animes.append(anime_entry)
                    continue
                anime = Anime(
                    mal_id=api_data.get("mal_id") or mal_id,
                    title=api_data.get("title") or anime_name,
                    rating=api_data.get("rating"),
                    quality="HD",  # default value
                    episode_count=api_data.get("episodes") or 0,
                    type=api_data.get("type"),
                    duration=api_data.get("duration"),
                    description=api_data.get("synopsis"),
                    japanese_title=api_data.get("title_japanese"),
                    synonyms=", ".join(api_data.get("title_synonyms") or []),
                    aired=api_data.get("aired", {}).get("string"),
                    premiered=api_data.get("season") or "",
                    status=api_data.get("status"),
                    mal_score=api_data.get("score") or 0.0,
                    genres=", ".join([genre.get("name") for genre in api_data.get("genres", [])]),
                    studios=", ".join([studio.get("name") for studio in api_data.get("studios", [])]),
                    producers=", ".join([producer.get("name") for producer in api_data.get("producers", [])]),
                    poster_image=api_data.get("images", {}).get("jpg", {}).get("large_image_url"),
                    portrait_image=(
                        api_data.get("trailer", {}).get("images", {}).get("maximum_image_url") or
                        api_data.get("images", {}).get("jpg", {}).get("large_image_url")
                    )
                )
            else:
                print(f"Error fetching MAL data for ID {mal_id}. Creating minimal entry for '{anime_name}'.")
                anime = Anime(
                    mal_id=mal_id,
                    title=anime_name,
                    poster_image=None
                )
        else:
            # No MAL code provided, create an anime with minimal info
            anime = Anime(
                mal_id=None,
                title=anime_name,
                poster_image=None
            )
        db.session.add(anime)
        db.session.commit()
        print(f"Added anime: '{anime.title}' (ID: {anime.id})")

    # Process episodes for this anime
    for ep_data in episodes_field:
        # Ensure episode data is a dictionary; if not, skip it.
        if not isinstance(ep_data, dict):
            skipped_episodes.append({
                "anime_name": anime_name,
                "episode_data": ep_data,
                "reason": "Episode data is not a dictionary"
            })
            print(f"  Skipping invalid episode data for anime '{anime_name}'.")
            continue

        # Check if embed sources indicate no links
        embed_srcs = ep_data.get("embed_srcs")
        if isinstance(embed_srcs, list) and len(embed_srcs) == 1 and embed_srcs[0] == "No embed links":
            skipped_episodes.append({
                "anime_name": anime_name,
                "episode": ep_data.get("episode"),
                "episode_url": ep_data.get("episode_url"),
                "reason": "No embed links"
            })
            print(f"  Skipping episode {ep_data.get('episode')} for anime '{anime_name}' due to no embed links.")
            continue

        # Process valid episode
        episode_number = ep_data.get("episode")
        episode_url = ep_data.get("episode_url")
        episode = Episode.query.filter_by(anime_id=anime.id, episode_number=episode_number).first()
        if not episode:
            episode = Episode(
                anime_id=anime.id,
                episode_number=episode_number,
                episode_url=episode_url
            )
            db.session.add(episode)
            db.session.commit()
            print(f"  Added episode {episode_number} for anime '{anime.title}'.")

        # Process each embed source for this episode
        for embed in embed_srcs:
            if not isinstance(embed, dict):
                skipped_episodes.append({
                    "anime_name": anime_name,
                    "episode": episode_number,
                    "embed_data": embed,
                    "reason": "Embed data is not a dictionary"
                })
                print(f"    Skipping invalid embed data for episode {episode_number} in anime '{anime_name}'.")
                continue

            server = embed.get("server")
            link = embed.get("link")
            if not server or not link:
                skipped_episodes.append({
                    "anime_name": anime_name,
                    "episode": episode_number,
                    "embed_data": embed,
                    "reason": "Missing server or link in embed data"
                })
                print(f"    Skipping embed for episode {episode_number} in anime '{anime_name}' due to missing server/link.")
                continue

            # Add embed only if it does not already exist
            existing_embed = EpisodeEmbed.query.filter_by(episode_id=episode.id, server=server).first()
            if not existing_embed:
                embed_obj = EpisodeEmbed(
                    episode_id=episode.id,
                    server=server,
                    link=link
                )
                db.session.add(embed_obj)
                print(f"    Added embed '{server}' for episode {episode_number}.")
        db.session.commit()

# Save skipped items to a JSON file
skipped_data = {
    "skipped_animes": skipped_animes,
    "skipped_episodes": skipped_episodes
}

with open("skipped.json", "w", encoding="utf-8") as outfile:
    json.dump(skipped_data, outfile, indent=4, ensure_ascii=False)

print("\nImport completed. Skipped items have been written to 'skipped.json'.")
