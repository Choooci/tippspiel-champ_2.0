import streamlit as st
from supabase import create_client, Client
import pandas as pd
import requests
import random

# --- SUPABASE INIT ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

st.set_page_config(page_title="Bundesliga Tippspiel 2.0", layout="wide")

# --- DATENBANKFUNKTIONEN ---

def get_or_create_season(season_name):
    try:
        result = supabase.table("seasons").select("*").eq("season_name", season_name).single().execute()
        return result.data
    except:
        new_season = supabase.table("seasons").insert({
            "season_name": season_name,
            "draft_completed": False,
            "draft_order": None,
            "draft_stage": "waiting"  # waiting, drawing, team_draft, completed
        }).execute()
        return new_season.data[0]

def get_players():
    try:
        result = supabase.table("players").select("*").execute()
        return result.data
    except:
        return []

def get_teams_for_season(season_id):
    try:
        result = supabase.table("teams").select("*").execute()
        return result.data
    except:
        return []

def get_draft_order(season_id):
    """Holt die ausgeloste Draft-Reihenfolge."""
    try:
        result = supabase.table("seasons").select("draft_order").eq("id", season_id).single().execute()
        return result.data.get("draft_order") if result.data else None
    except Exception as e:
        return None

def save_draft_order(season_id, draft_order):
    """Speichert die ausgeloste Draft-Reihenfolge."""
    try:
        supabase.table("seasons").update({"draft_order": draft_order}).eq("id", season_id).execute()
        st.success("Draft-Reihenfolge gespeichert!")
    except Exception as e:
        st.error(f"Fehler beim Speichern: {str(e)}")

def get_draft_stage(season_id):
    """Holt aktuellen Draft-Status."""
    try:
        result = supabase.table("seasons").select("draft_stage").eq("id", season_id).single().execute()
        return result.data.get("draft_stage") if result.data else "waiting"
    except:
        return "waiting"

def update_draft_stage(season_id, stage):
    """Updated Draft-Status."""
    try:
        supabase.table("seasons").update({"draft_stage": stage}).eq("id", season_id).execute()
    except Exception as e:
        st.error(f"Fehler: {str(e)}")

def complete_draft(season_id):
    """Beendet den Draft."""
    try:
        supabase.table("seasons").update({
            "draft_completed": True,
            "draft_stage": "completed"
        }).eq("id", season_id).execute()
        st.success("Draft abgeschlossen!")
    except Exception as e:
        st.error(f"Fehler: {str(e)}")

def get_draft_picks(season_id):
    """Holt alle Draft-Picks."""
    try:
        result = supabase.table("draft_picks").select("*").eq("season_id", season_id).order("pick_order").execute()
        return result.data
    except:
        return []

def save_draft_pick(season_id, player_id, team_id, pick_order):
    """Speichert einen Draft-Pick."""
    try:
        supabase.table("draft_picks").insert({
            "season_id": season_id,
            "player_id": player_id,
            "team_id": team_id,
            "pick_order": pick_order
        }).execute()
    except Exception as e:
        st.error(f"Fehler beim Speichern des Picks: {str(e)}")

def get_bundesliga_table():
    """Lädt aktuelle Bundesliga-Tabelle von OpenLigaDB."""
    try:
        url = "https://www.openligadb.de/api/getbltable/bl1/2026"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

# --- HAUPTAPP ---

st.title("⚽ Bundesliga Tippspiel 2.0")

season = get_or_create_season(AKTUELLE_SAISON)
season_id = season["id"]
draft_stage = get_draft_stage(season_id)

st.subheader(f"Saison {AKTUELLE_SAISON}")

# --- SPIELER-AUSWAHL ---
if "current_player" not in st.session_state:
    st.session_state.current_player = None

players = get_players()
player_names = [p["name"] for p in players]

selected_player = st.selectbox("Wer bist du?", player_names, key="player_select")
if selected_player:
    st.session_state.current_player = selected_player

is_admin = st.session_state.current_player == "Choci"

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["🎲 Draft", "📊 Tabelle & Ergebnisse", "⚙️ Admin"])

# ============ TAB 1: DRAFT ============
with tab1:
    if draft_stage == "waiting":
        st.info("⏳ Warte auf Draft-Verlosung...")
        
        # Nur Choci sieht den Button
        if is_admin:
            st.warning("Du bist Admin – Du kannst die Verlosung starten!")
            if st.button("🎲 Draft-Reihenfolge auslosen", key="draw_button"):
                # Spieler zufällig sortieren
                shuffled_players = player_names.copy()
                random.shuffle(shuffled_players)
                draft_order_str = "".join([str(player_names.index(p) + 1) for p in shuffled_players])
                
                save_draft_order(season_id, draft_order_str)
                update_draft_stage(season_id, "drawing")
                st.rerun()

    elif draft_stage == "drawing":
        st.success("✅ Draft-Reihenfolge wurde ausgelost!")
        
        draft_order = get_draft_order(season_id)
        
        # Zeige die Draft-Reihenfolge an
        st.subheader("Draft-Reihenfolge:")
        if draft_order:
            order_list = [int(d) for d in draft_order[:len(players)]]
            col1, col2 = st.columns(2)
            with col1:
                for i, pos in enumerate(order_list[:len(players)//2 + 1], 1):
                    st.write(f"**Pick {i}:** {player_names[pos-1]}")
            with col2:
                for i, pos in enumerate(order_list[len(players)//2 + 1:], len(players)//2 + 2):
                    st.write(f"**Pick {i}:** {player_names[pos-1]}")
        
        # Nur Choci kann weiter machen
        if is_admin:
            if st.button("➡️ Jetzt zum Team-Draft", key="start_draft"):
                update_draft_stage(season_id, "team_draft")
                st.rerun()
        else:
            st.info("Warte bis Choci zum Team-Draft weitergeht...")

    elif draft_stage == "team_draft":
        st.subheader("🎯 Team-Draft läuft!")
        
        teams = get_teams_for_season(season_id)
        draft_picks = get_draft_picks(season_id)
        draft_order = get_draft_order(season_id)
        
        # Zeige bisherige Picks
        if draft_picks:
            st.write("**Bisherige Picks:**")
            for pick in draft_picks:
                player = next((p for p in players if p["id"] == pick["player_id"]), None)
                team = next((t for t in teams if t["id"] == pick["team_id"]), None)
                st.write(f"Pick {pick['pick_order']}: {player['name']} → {team['name']}")
        
        # Aktuelle Pick-Nummer
        current_pick_num = len(draft_picks) + 1
        if current_pick_num <= len(draft_order):
            order_list = [int(d) for d in draft_order]
            current_player_idx = order_list[current_pick_num - 1] - 1
            current_player_name = player_names[current_player_idx]
            
            st.info(f"**Jetzt am Zug:** {current_player_name}")
            
            # Nur der aktuelle Spieler kann picken
            if st.session_state.current_player == current_player_name:
                available_teams = [t for t in teams if not any(p["team_id"] == t["id"] for p in draft_picks)]
                if available_teams:
                    team_names = [t["name"] for t in available_teams]
                    selected_team = st.selectbox(f"Pick {current_pick_num}: Wähle Dein Team", team_names)
                    
                    if st.button("✅ Team picken"):
                        team = next(t for t in available_teams if t["name"] == selected_team)
                        player = next(p for p in players if p["name"] == st.session_state.current_player)
                        save_draft_pick(season_id, player["id"], team["id"], current_pick_num)
                        st.success(f"Du hast {selected_team} gepickt!")
                        st.rerun()
                else:
                    st.success("🎉 Alle Teams wurden gepickt!")
            else:
                st.write(f"Warte bis {current_player_name} sein Team pickt...")

    elif draft_stage == "completed":
        st.success("✅ Draft abgeschlossen!")
        draft_picks = get_draft_picks(season_id)
        st.write("**Finale Draft-Ergebnisse:**")
        for pick in draft_picks:
            player = next((p for p in players if p["id"] == pick["player_id"]), None)
            team = next((t for t in teams if t["id"] == pick["team_id"]), None)
            st.write(f"**{player['name']}** → {team['name']}")

# ============ TAB 2: TABELLE & ERGEBNISSE ============
with tab2:
    st.subheader("📊 Bundesliga-Tabelle 2026-27")
    
    table_data = get_bundesliga_table()
    
    if table_data:
        st.dataframe(
            [
                {
                    "Platz": t["shortTableType"],
                    "Team": t["teamName"],
                    "Spiele": t["matches"],
                    "W": t["won"],
                    "U": t["draw"],
                    "V": t["lost"],
                    "Tore": f"{t['goalsFavor']}:{t['goalsAgainst']}",
                    "Punkte": t["points"]
                }
                for t in sorted(table_data, key=lambda x: x["points"], reverse=True)
            ],
            use_container_width=True
        )
    else:
        st.warning("Konnte Tabelle nicht laden...")

# ============ TAB 3: ADMIN ============
with tab3:
    if is_admin:
        st.subheader("⚙️ Admin-Bereich")
        
        st.write(f"**Aktueller Draft-Status:** {draft_stage}")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Draft zurücksetzen"):
                supabase.table("draft_picks").delete().eq("season_id", season_id).execute()
                update_draft_stage(season_id, "waiting")
                supabase.table("seasons").update({"draft_order": None}).eq("id", season_id).execute()
                st.success("Draft zurückgesetzt!")
                st.rerun()
        
        with col2:
            if st.button("✅ Draft beenden"):
                complete_draft(season_id)
                st.rerun()
        
        with col3:
            st.write("(Weitere Admin-Funktionen hier)")
    else:
        st.error("❌ Du bist kein Admin!")
