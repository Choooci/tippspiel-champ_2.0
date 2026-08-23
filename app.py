# app.py
# Bundesliga Tippspiel 2.0 - mit Supabase Datenbank

import streamlit as st
import pandas as pd
import requests
from supabase import create_client, Client
import random
from datetime import datetime

# --- Verbindung zu Supabase herstellen ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# --- Seiteneinstellungen ---
st.set_page_config(page_title="Bundesliga Tippspiel 2.0", layout="wide")

# --- Passwortschutz ---
PASSWORT = "040822"
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Bundesliga Tippspiel 2.0")
    pw_input = st.text_input("Passwort eingeben", type="password")
    if st.button("Einloggen"):
        if pw_input == PASSWORT:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Falsches Passwort")
    st.stop()

# --- Die feste Snake-Draft-Reihenfolge ---
# Pick 1: Spieler auf Position 1
# Pick 2: Spieler auf Position 2
# ...
# Pick 5: Spieler auf Position 4 (umgekehrt!)
# Pick 6: Spieler auf Position 3
# etc.
SNAKE_DRAFT_ORDER = "1234432112344321"

# --- API für aktuelle Bundesliga-Tabelle ---
def get_current_season_from_api():
    """Holt die aktuelle Saison von OpenLigaDB."""
    try:
        response = requests.get("https://www.openligadb.de/api/getbltable/bl1/2025")
        return response.status_code == 200
    except:
        return False

# --- Hilfsfunktionen ---

def get_active_season():
    """Holt die aktive Saison."""
    result = supabase.table("seasons").select("*").eq("is_active", True).execute()
    if len(result.data) > 0:
        return result.data[0]
    else:
        st.error("Keine aktive Saison gefunden!")
        return None

def get_players():
    """Holt alle Spieler."""
    result = supabase.table("players").select("*").order("id").execute()
    return result.data

def get_teams_for_season(season_id):
    """Holt alle Teams für eine Saison."""
    result = supabase.table("teams").select("*").eq("season_id", season_id).execute()
    return result.data

def get_draft_order(season_id):
    """Holt die ausgeloste Draft-Reihenfolge (wer sitzt auf Position 1-4)."""
    result = supabase.table("draft_order").select("*, players(name)").eq("season_id", season_id).order("position").execute()
    return result.data

def get_draft_picks(season_id):
    """Holt alle bisherigen Draft-Picks."""
    result = supabase.table("draft_picks").select("*, players(name), teams(team_name, logo_url)").eq("season_id", season_id).order("pick_order").execute()
    return result.data

def save_draft_order(season_id, player_ids):
    """Speichert die ausgeloste Reihenfolge (Position 1-4)."""
    # Spieler-IDs zufällig mischen
    shuffled = player_ids.copy()
    random.shuffle(shuffled)
    
    # In die DB schreiben
    for position, player_id in enumerate(shuffled, start=1):
        supabase.table("draft_order").insert({
            "season_id": season_id,
            "player_id": player_id,
            "position": position
        }).execute()

def save_draft_pick(season_id, player_id, team_id, pick_order):
    """Speichert einen einzelnen Draft-Pick."""
    supabase.table("draft_picks").insert({
        "season_id": season_id,
        "player_id": player_id,
        "team_id": team_id,
        "pick_order": pick_order
    }).execute()

def get_next_pick_info(season_id, draft_order, current_pick_number):
    """Ermittelt, welcher Spieler beim nächsten Pick dran ist."""
    # Position aus der Snake-Draft-Reihenfolge (1-4)
    position_char = SNAKE_DRAFT_ORDER[(current_pick_number - 1) % len(SNAKE_DRAFT_ORDER)]
    position = int(position_char)
    
    # Spieler mit dieser Position finden
    player = next((p for p in draft_order if p["position"] == position), None)
    return player

def mark_draft_completed(season_id):
    """Markiert den Draft als abgeschlossen."""
    supabase.table("seasons").update({"is_active": False}).eq("id", season_id).execute()

# --- HAUPTAPP ---

st.title("⚽ Bundesliga Tippspiel 2.0")

# Aktive Saison laden
season = get_active_season()
if not season:
    st.stop()

season_id = season["id"]
st.subheader(f"Saison {season['name']}")

# --- DRAFT-BEREICH ---
st.header("🎲 Team-Draft")

players = get_players()
teams = get_teams_for_season(season_id)

if len(teams) == 0:
    st.error("Keine Teams für diese Saison hinterlegt!")
    st.stop()

# Schritt 1: Draft-Reihenfolge auslosen
draft_order = get_draft_order(season_id)

if len(draft_order) == 0:
    st.info("Schritt 1: Reihenfolge auslosen")
    if st.button("🎲 Reihenfolge auslosen!"):
        player_ids = [p["id"] for p in players]
        save_draft_order(season_id, player_ids)
        st.rerun()
else:
    # Reihenfolge anzeigen
    st.write("**📍 Ausgeloste Reihenfolge:**")
    cols = st.columns(len(draft_order))
    for idx, entry in enumerate(draft_order):
        with cols[idx]:
            st.metric(f"Pos. {entry['position']}", entry["players"]["name"])

    # Schritt 2: Der eigentliche Draft
    picks = get_draft_picks(season_id)
    picked_team_ids = {p["team_id"] for p in picks}
    available_teams = [t for t in teams if t["id"] not in picked_team_ids]
    
    current_pick_number = len(picks) + 1
    total_teams = len(teams)

    st.write("---")
    st.write(f"**Pick {current_pick_number} von {total_teams}**")

    if current_pick_number <= total_teams:
        # Wer ist dran?
        next_player = get_next_pick_info(season_id, draft_order, current_pick_number)
        
        if next_player:
            st.write(f"### 🎯 **{next_player['players']['name']} ist dran!**")
            
            # Teams in einem Grid anzeigen
            cols = st.columns(6)
            for idx, team in enumerate(available_teams):
                with cols[idx % 6]:
                    st.write(f"**{team['team_name']}**")
                    if team.get("logo_url"):
                        st.image(team["logo_url"], width=100)
                    if st.button("Wählen", key=f"pick_{team['id']}"):
                        save_draft_pick(season_id, next_player["player_id"], team["id"], current_pick_number)
                        st.rerun()
    else:
        st.success("✅ Alle Teams wurden gepickt!")
        if st.button("🚀 Draft abschließen & Saison starten"):
            mark_draft_completed(season_id)
            st.rerun()

    # Bisherige Picks anzeigen
    if len(picks) > 0:
        st.write("---")
        st.write("**📋 Bisherige Picks:**")
        picks_df = pd.DataFrame([{
            "Pick": p["pick_order"],
            "Spieler": p["players"]["name"],
            "Team": p["teams"]["team_name"]
        } for p in picks])
        st.dataframe(picks_df, use_container_width=True, hide_index=True)

# --- Nach Draft: Saison läuft ---
st.write("---")
st.write("🏆 Saison-Übersicht kommt bald...")
