import requests
import os

def get_ytmusic_user_data(access_token: str):
    """Extrae actividad musical desde YouTube Data API."""
    headers = {"Authorization": f"Bearer {access_token}"}
    yt_base_url = "https://www.googleapis.com/youtube/v3"
    
    try:
        playlists_res = requests.get(
            f"{yt_base_url}/playlists?part=snippet&mine=true&maxResults=10",
            headers=headers
        )
        playlists_data = playlists_res.json()
        
        user_playlists = []
        if "items" in playlists_data:
            for item in playlists_data["items"]:
                user_playlists.append(item["snippet"]["title"])

        likes_res = requests.get(
            f"{yt_base_url}/videos?part=snippet&myRating=like&maxResults=50",
            headers=headers
        )
        likes_data = likes_res.json()
        
        liked_songs = []
        if "items" in likes_data:
            for item in likes_data["items"]:
                snippet = item.get("snippet", {})
                
                if snippet.get("categoryId") == "10":
                    liked_songs.append(snippet.get("title"))
                    
                if len(liked_songs) >= 10:
                    break

        return {
            "playlists": user_playlists,
            "recent_likes": liked_songs
        }

    except Exception as e:
        print(f"🔴 Error extrayendo datos de YT Music: {e}")
        return None

def refresh_google_token(refresh_token: str):
    """Refresca token de Google."""
    url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    
    response = requests.post(url, data=data)
    return response.json()

def check_and_refresh_yt_token(user_id: str):
    """Verifica validez de token Google, refresca según necesidad."""
    from database import get_user_token, update_user_auth_data
    
    auth_data = get_user_token(user_id)
    if not auth_data or "refresh_token" not in auth_data:
        return None

    new_tokens = refresh_google_token(auth_data["refresh_token"])
    
    if "access_token" in new_tokens:
        auth_data.update({
            "access_token": new_tokens["access_token"],
            "expires_in": new_tokens.get("expires_in", 3600)
        })
        update_user_auth_data(user_id, auth_data)
        return auth_data["access_token"]
    
    return None