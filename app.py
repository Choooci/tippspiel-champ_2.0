# app.py
# Bundesliga Tippspiel 2.0 - mit Draft, Top-6 und Live-Tabelle

import streamlit as st
import pandas as pd
import requests
from supabase import create_client, Client
from datetime import datetime
import time

# --- Verbindung zu Supabase ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# --- Seiteneinstellungen ---
st.set_page_config(page_title="Bundesliga Tippspiel 2.0", layout="wide")

# --- Passwortschutz ---
PASSWORT = "040822"
SNAKE_DRAFT_ORDER = "1234432112344321"

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

# ============================================
# DATENBANK-FUNKTIONEN
# ============================================

def get_all_seasons():
    """Alle Saisons (für Dropdown)."""
    result = supabase.table("seasons").select("*").order("name", desc=True).execute()
    return result.data if result.data else []

def get_season(season_id):
    """Eine einzelne Saison."""
    result = supabase.table("seasons").select("*").eq("id", season_id).single().execute()
    return result.data

def get_players():
    """Alle 4 Spieler."""
    result = supabase.table("players").select("*").execute()
    return result.data if result.data else []

def get_teams_for_season(season_id):
    """Alle 18 Teams für eine Saison."""
    result = supabase.table("teams").select("*").eq("season_id", season_id).execute()
    return result.data if result.data else []

def get_draft_order(season_id):
    """Draft-Reihenfolge für diese Saison."""
    result = supabase.table("draft_order").select("*,players(*)").eq("season_id", season_id).order("position").execute()
    return result.data if result.data else []

def get_draft_picks(season_id):
    """Alle bisherigen Picks."""
    result = supabase.table("draft_picks").select("*,players(*),teams(*)").eq("season_id", season_id).order("pick_order").execute()
    return result.data if result.data else []

def save_draft_pick(season_id, player_id, team_id, pick_order):
    """Einen Pick speichern."""
    supabase.table("draft_picks").insert({
        "season_id": season_id,
        "player_id": player_id,
        "team_id": team_id,
        "pick_order": pick_order
    }).execute()

def mark_draft_completed(season_id):
    """Draft als abgeschlossen markieren."""
    supabase.table("seasons").update({"draft_completed": True}).eq("id", season_id).execute()

def get_top6_tips_for_player(season_id, player_id):
    """Top-6-Tipps eines Spielers."""
    result = supabase.table("top6_tips").select("*,teams(*)").eq("season_id", season_id).eq("player_id", player_id).execute()
    return result.data if result.data else []

def save_top6_tip(season_id, player_id, team_id, position):
    """Eine Top-6-Tipp speichern."""
    try:
        supabase.table("top6_tips").insert({
            "season_id": season_id,
            "player_id": player_id,
            "team_id": team_id,
            "predicted_position": position
        }).execute()
        return True
    except Exception as e:
        st.error(f"Fehler beim Speichern: {str(e)}")
        return False

def delete_top6_tip(season_id, player_id, position):
    """Eine Top-6-Tipp löschen."""
    supabase.table("top6_tips").delete().eq("season_id", season_id).eq("player_id", player_id).eq("predicted_position", position).execute()

# ============================================
# OpenLigaDB API
# ============================================

@st.cache_data(ttl=300)  # 5 Minuten cachen
def get_bundesliga_table():
    """Holt aktuelle Tabelle von OpenLigaDB (Saison 2024/25)."""
    try:
        response = requests.get("https://www.openligadb.de/api/getbltable/bl1/2024")
        if response.status_code == 200:
            table = response.json()
            # Sortieren nach Platzierung
            table_sorted = sorted(table, key=lambda x: x.get("shortName", ""), reverse=False)
            return table_sorted
        else:
            return None
    except Exception as e:
        st.error(f"API-Fehler: {e}")
        return None

# ============================================
# SEITEN-LOGIK
# ============================================

st.title("⚽ Bundesliga Tippspiel 2.0")

# --- Saison-Auswahl ---
all_seasons = get_all_seasons()
if not all_seasons:
    st.error("Keine Saisons in der Datenbank!")
    st.stop()

season_names = [s["name"] for s in all_seasons]
selected_season_name = st.selectbox("Saison wählen", season_names)
season = next(s for s in all_seasons if s["name"] == selected_season_name)
season_id = season["id"]

st.subheader(f"Saison {season['name']}")

# ============================================
# TAB 1: DRAFT (nur wenn nicht abgeschlossen)
# ============================================

if not season.get("draft_completed", False):
    st.header("🎲 Team-Draft")
    
    players = get_players()
    teams = get_teams_for_season(season_id)
    draft_order = get_draft_order(season_id)
    draft_picks = get_draft_picks(season_id)
    
    if len(teams) == 0:
        st.warning("⚠️ Für diese Saison sind noch keine Teams hinterlegt.")
        st.stop()
    
    # --- Picks anzeigen ---
    if len(draft_picks) > 0:
        st.write("**📋 Bisherige Picks:**")
        picks_df = pd.DataFrame([{
            "Pick #": p["pick_order"],
            "Spieler": p["players"]["name"],
            "Team": p["teams"]["team_name"]
        } for p in draft_picks])
        st.dataframe(picks_df, use_container_width=True, hide_index=True)
    
    # --- Nächster Pick ---
    next_pick_number = len(draft_picks) + 1
    total_picks_needed = len(players) * len(teams)  # 4 Spieler × 18 Teams = 72 Picks
    
    if next_pick_number <= total_picks_needed:
        # Berechne, welcher Spieler jetzt dran ist (Snake-Draft)
        position_in_round = ((next_pick_number - 1) % len(players))
        round_number = (next_pick_number - 1) // len(players)
        
        # Snake-Logik: ungerade Runden normal, gerade Runden umgekehrt
        if round_number % 2 == 0:  # Ungerade Runde (1, 3, 5...)
            player_index = int(SNAKE_DRAFT_ORDER[position_in_round]) - 1
        else:  # Gerade Runde (2, 4, 6...)
            player_index = int(SNAKE_DRAFT_ORDER[3 - position_in_round]) - 1
        
        next_player = players[player_index]
        
        # Teams, die noch nicht gepickt wurden
        picked_team_ids = [p["team_id"] for p in draft_picks]
        available_teams = [t for t in teams if t["id"] not in picked_team_ids]
        
        st.info(f"🎯 **{next_player['name']}** ist dran! ({next_pick_number}/{total_picks_needed})")
        
        st.write(f"**Verfügbare Teams ({len(available_teams)}):**")
        
        cols = st.columns(3)
        for idx, team in enumerate(available_teams):
            with cols[idx % 3]:
                with st.container(border=True):
                    # Logo
                    try:
                        st.image(team["logo_url"], width=100)
                    except:
                        st.text("❌ Logo")
                    
                    st.write(f"**{team['team_name']}**")
                    
                    if st.button("Wählen", key=f"pick_{team['id']}"):
                        save_draft_pick(season_id, next_player["id"], team["id"], next_pick_number)
                        st.success(f"✅ {next_player['name']} hat {team['team_name']} gepickt!")
                        time.sleep(1)
                        st.rerun()
    else:
        st.success("✅ Draft abgeschlossen!")
        if st.button("🚀 Saison starten"):
            mark_draft_completed(season_id)
            st.rerun()

# ============================================
# TAB 2: TOP-6-TIPPS (nach Draft)
# ============================================

else:
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("⭐ Top-6-Tipps")
        
        players = get_players()
        player_names = [p["name"] for p in players]
        selected_player_name = st.selectbox("Spieler auswählen", player_names, key="top6_player")
        selected_player = next(p for p in players if p["name"] == selected_player_name)
        
        teams = get_teams_for_season(season_id)
        player_tips = get_top6_tips_for_player(season_id, selected_player["id"])
        
        st.write("---")
        st.write(f"**Deine Tipps ({len(player_tips)}/6):**")
        
        # Bisherige Tipps anzeigen
        for position in range(1, 7):
            tip = next((t for t in player_tips if t["predicted_position"] == position), None)
            
            if tip:
                col_img, col_name, col_delete = st.columns([1, 3, 1])
                with col_img:
                    try:
                        st.image(tip["teams"]["logo_url"], width=60)
                    except:
                        st.text("❌")
                with col_name:
                    st.write(f"**Platz {position}: {tip['teams']['team_name']}**")
                with col_delete:
                    if st.button("❌", key=f"delete_{position}"):
                        delete_top6_tip(season_id, selected_player["id"], position)
                        st.rerun()
            else:
                st.write(f"Platz {position}: *noch nicht gesetzt*")
        
        st.write("---")
        
        # Neuen Tipp hinzufügen
        if len(player_tips) < 6:
            st.write("**Neuen Tipp hinzufügen:**")
            
            # Nur freie Positionen anzeigen
            free_positions = [p for p in range(1, 7) if not any(t["predicted_position"] == p for t in player_tips)]
            selected_position = st.selectbox("Position", free_positions, key="new_position")
            
            # Nur Teams anzeigen, die noch nicht getippt wurden
            tipped_team_ids = [t["team_id"] for t in player_tips]
            available_teams = [t for t in teams if t["id"] not in tipped_team_ids]
            
            team_names = [t["team_name"] for t in available_teams]
            selected_team_name = st.selectbox("Team", team_names, key="new_team")
            selected_team = next(t for t in available_teams if t["team_name"] == selected_team_name)
            
            if st.button("✅ Tipp speichern"):
                if save_top6_tip(season_id, selected_player["id"], selected_team["id"], selected_position):
                    st.success(f"Platz {selected_position}: {selected_team['team_name']} gespeichert!")
                    time.sleep(1)
                    st.rerun()
    
    # ============================================
    # TAB 3: BUNDESLIGA-TABELLE (Live)
    # ============================================
    
    with col2:
        st.header("🏆 Aktuelle Bundesliga-Tabelle")
        
        table_data = get_bundesliga_table()
        
        if table_data:
            # DataFrame bauen
            table_df = pd.DataFrame([{
                "Platz": t.get("Tabellenplatz", "-"),
                "Team": t.get("TeamName", "Unknown"),
                "Spiele": t.get("Spiele", 0),
                "Sieg": t.get("Siege", 0),
                "Unent.": t.get("Unentschieden", 0),
                "Niederl.": t.get("Niederlagen", 0),
                "Tore": f"{t.get('Torverhaeltnis', '0:0')}",
                "Punkte": t.get("Punkte", 0)
            } for t in table_data])
            
            st.dataframe(table_df, use_container_width=True, hide_index=True)
            
            st.caption("🔄 Aktualisiert alle 5 Minuten")
        else:
            st.error("Konnte Tabelle nicht laden. Später nochmal versuchen.")
