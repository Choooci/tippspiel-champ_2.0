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
st.title("⚽ Bundesliga Tippspiel 2.0")

# --- Konstanten ---
PASSWORT = "040822"
SNAKE_DRAFT_ORDER = "1234432112344321"
AKTUELLE_SAISON = "2026/27"

# ============================================
# DATENBANK-FUNKTIONEN
# ============================================

def get_all_seasons():
    """Alle Saisons."""
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
    """Holt die ausgeloste Draft-Reihenfolge."""
    try:
        result = supabase.table("seasons").select("draft_order").eq("id", season_id).single().execute()
        return result.data.get("draft_order") if result.data else None
    except Exception as e:
        st.error(f"Fehler beim Abrufen der Draft-Reihenfolge: {str(e)}")
        return None

def save_draft_order(season_id, draft_order):
    """Speichert die ausgeloste Draft-Reihenfolge."""
    try:
        supabase.table("seasons").update({"draft_order": draft_order}).eq("id", season_id).execute()
    except Exception as e:
        st.error(f"Fehler beim Speichern der Draft-Reihenfolge: {str(e)}")



def get_top6_tips_for_player(season_id, player_id):
    """Top-6 Tipps eines Spielers."""
    result = supabase.table("top6_tips").select("*").eq("season_id", season_id).eq("player_id", player_id).execute()
    return result.data if result.data else []

def save_top6_tip(season_id, player_id, team_id, position):
    """Einen Top-6 Tipp speichern."""
    try:
        result = supabase.table("top6_tips").insert({
            "season_id": season_id,
            "player_id": player_id,
            "team_id": team_id,
            "predicted_position": position
        }).execute()
        return True
    except Exception as e:
        st.error(f"Fehler beim Speichern: {str(e)}")
        return False

def delete_top6_tip(tip_id):
    """Einen Tipp löschen."""
    try:
        supabase.table("top6_tips").delete().eq("id", tip_id).execute()
        return True
    except Exception as e:
        st.error(f"Fehler beim Löschen: {str(e)}")
        return False

def get_bundesliga_table():
    """Live-Tabelle von OpenLigaDB laden."""
    try:
        url = "https://www.openligadb.de/api/Clubtable/BL1/2026"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        st.error(f"Fehler beim Laden der Tabelle: {str(e)}")
        return None



# ============================================
# SEITENLOGIK
# ============================================

# Passwortschutz
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        pw_input = st.text_input("🔒 Passwort eingeben", type="password")
        if st.button("Einloggen"):
            if pw_input == PASSWORT:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Falsches Passwort")
    st.stop()

# Saison wählen
seasons = get_all_seasons()
season_names = [s["name"] for s in seasons]

col1, col2 = st.columns([3, 1])
with col1:
    selected_season_name = st.selectbox("Saison wählen", season_names, index=0)
    selected_season = next((s for s in seasons if s["name"] == selected_season_name), None)
    season_id = selected_season["id"]

# Spieler wählen
players = get_players()
player_names = [p["name"] for p in players]
selected_player_name = st.selectbox("Spieler wählen", player_names)
selected_player = next((p for p in players if p["name"] == selected_player_name), None)

st.divider()


# ============================================
# DRAFT-REIHENFOLGE AUSLOSEN
# ============================================

st.divider()
st.header("🎰 Draft-Reihenfolge auslosen")

draft_order = get_draft_order(season_id)

if not draft_order:
    st.warning("⚠️ Draft-Reihenfolge wurde noch nicht ausgelost!")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🎲 REIHENFOLGE AUSLOSEN", use_container_width=True, type="primary"):
            import random
            
            # Spieler shufflen
            shuffled_players = players.copy()
            random.shuffle(shuffled_players)
            draft_order = [p["id"] for p in shuffled_players]
            
            # Speichern
            save_draft_order(season_id, draft_order)
            st.session_state.show_draw = True
            st.rerun()
    
    # Spannende Animation wenn gerade ausgelost
    if st.session_state.get("show_draw", False):
        st.balloons()
        time.sleep(0.5)
else:
    # Reihenfolge anzeigen
    st.success("✅ Draft-Reihenfolge wurde ausgelost!")
    
    col1, col2, col3, col4 = st.columns(4)
    for idx, player_id in enumerate(draft_order):
        player = next((p for p in players if p["id"] == player_id), None)
        if player:
            cols = [col1, col2, col3, col4]
            with cols[idx % 4]:
                st.markdown(f"""
                <div style='text-align: center; padding: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; color: white;'>
                    <h3 style='margin: 0; font-size: 2em;'>#{idx + 1}</h3>
                    <p style='margin: 10px 0 0 0; font-size: 1.2em;'><b>{player['name']}</b></p>
                </div>
                """, unsafe_allow_html=True)
    
    st.divider()

st.divider()


# Tabs
tab1, tab2, tab3 = st.tabs(["🎲 Draft", "📊 Top-6 Tipps", "🏆 Bundesliga-Tabelle"])

def get_draft_order(season_id):
    """Holt die ausgeloste Draft-Reihenfolge."""
    result = supabase.table("seasons").select("draft_order").eq("id", season_id).single().execute()
    return result.data.get("draft_order") if result.data else None

def save_draft_order(season_id, draft_order):
    """Speichert die ausgeloste Draft-Reihenfolge."""
    supabase.table("seasons").update({"draft_order": draft_order}).eq("id", season_id).execute()


# ============================================
# TAB 1: DRAFT
# ============================================

with tab1:
    st.header("🎲 Team-Draft")
    
    teams = get_teams_for_season(season_id)
    
    if not teams:
        st.warning("⚠️ Für diese Saison sind noch keine Teams in der Datenbank.")
        st.stop()
    
    # Draft-Status abrufen
    season = get_season(season_id)
    draft_completed = season.get("draft_completed", False)
    
    if draft_completed:
        st.success("✅ Draft abgeschlossen!")
        st.info("Alle Teams wurden gepickt. Die Saison kann starten!")
    else:
        st.subheader("📋 Draft-Reihenfolge")
        
        # Alle Picks abrufen
        response = supabase.table('player_picks').select('*').eq('season_id', season_id).order('pick_order', desc=False).execute()
        all_picks = response.data if response.data else []
        
        # Nächste Pick-Nummer ermitteln
        next_pick_number = len(all_picks) + 1
        total_teams = 16  # NUR 16 TEAMS STATT 18
        
        # Wer ist dran? (Snake-Draft-Reihenfolge)
        if next_pick_number <= total_teams:
            # Position aus Snake-Draft ermitteln (0-basiert)
            draft_position = int(SNAKE_DRAFT_ORDER[(next_pick_number - 1) % len(SNAKE_DRAFT_ORDER)])
            current_player = players[draft_position - 1]  # 1-basiert zu 0-basiert
            
            st.info(f"🎯 **{current_player['name']}** ist dran! (Pick {next_pick_number}/{total_teams})")
            
            # Bereits gepickte Teams ausblenden
            picked_team_ids = [p["team_id"] for p in all_picks]
            available_teams = sorted([t for t in teams if t["id"] not in picked_team_ids], 
                                   key=lambda x: x["team_name"])
            
            # Team-Auswahl (nur wenn der richtige Spieler eingeloggt ist)
            if selected_player["id"] == current_player["id"]:
                st.subheader(f"🎪 Wähle dein Team")
                
                # Logo-Vorschau
                st.write("**Team-Logos:**")
                cols = st.columns(4)
                for idx, team in enumerate(available_teams):
                    with cols[idx % 4]:
                        st.image(team['logo_url'], width=100)
                
                st.divider()
                
                # Dropdown nur
                team_options = [f"{t['team_name']}" for t in available_teams]
                selected_team_name = st.selectbox("Team auswählen", team_options)
                selected_team = next(t for t in available_teams if t["team_name"] == selected_team_name)
                
                if st.button("✅ Team picken!", use_container_width=True, type="primary"):
                    try:
                        supabase.table("player_picks").insert({
                            "season_id": season_id,
                            "player_id": current_player["id"],
                            "team_id": selected_team["id"],
                            "pick_order": next_pick_number
                        }).execute()
                        st.success(f"✅ {current_player['name']} hat {selected_team['team_name']} gepickt!")
                        time.sleep(2)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Speichern: {str(e)}")
            else:
                st.warning(f"⏳ Warte, bis {current_player['name']} pickt...")
        
        # Bisher gepickte Teams anzeigen
        st.divider()
        st.subheader("📌 Bisherige Picks")
        
        if all_picks:
            teams_dict = {t["id"]: t for t in teams}
            players_dict = {p["id"]: p for p in players}
            
            for pick in all_picks:
                team = teams_dict.get(pick["team_id"])
                player = players_dict.get(pick["player_id"])
                if team and player:
                    col1, col2, col3, col4 = st.columns([1, 2, 2, 1])
                    with col1:
                        st.write(f"**Pick {pick['pick_order']}**")
                    with col2:
                        st.write(player['name'])
                    with col3:
                        st.write(f"→ {team['team_name']}")
                    with col4:
                        if st.button("🗑️", key=f"delete_pick_{pick['id']}", help="Pick löschen"):
                            try:
                                supabase.table("player_picks").delete().eq("id", pick["id"]).execute()
                                st.success("Pick gelöscht!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Fehler beim Löschen: {str(e)}")
        else:
            st.info("Noch keine Teams gepickt.")
    
# ============================================
# GEPICKTE TEAMS ANZEIGEN
# ============================================

st.subheader(f"📌 Gepickte Teams – {selected_player_name}")

# Gepickte Teams aus Datenbank abrufen
response = supabase.table('player_picks').select('*').eq('season_id', season_id).eq('player_id', selected_player["id"]).order('pick_order', desc=False).execute()
gepickte_teams = response.data if response.data else []

if gepickte_teams:
    # Teams-Mapping erstellen für schnelle Zuordnung
    teams_dict = {t["id"]: t for t in teams}
    
    # Gepickte Teams in Spalten darstellen
    cols = st.columns(len(gepickte_teams))
    for idx, pick in enumerate(gepickte_teams):
        team = teams_dict.get(pick["team_id"])
        if team:
            with cols[idx]:
                st.markdown(f"""
                <div style='text-align: center; padding: 10px; border: 2px solid #1f77b4; border-radius: 8px;'>
                    <h4>Pick {pick['pick_order']}</h4>
                    <img src='{team['logo_url']}' width='80' style='margin: 10px 0;'><br>
                    <b>{team['team_name']}</b>
                </div>
                """, unsafe_allow_html=True)
else:
    st.info("📭 Noch keine Teams gepickt.")

# ============================================
# TAB 2: TOP-6 TIPPS
# ============================================

with tab2:
    st.header(f"📊 Top-6 Tipps – {selected_player_name}")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Deine Tipps")
        player_tips = get_top6_tips_for_player(season_id, selected_player["id"])
        
        if player_tips:
            for tip in sorted(player_tips, key=lambda x: x["predicted_position"]):
                team = next((t for t in teams if t["id"] == tip["team_id"]), None)
                team_name = team["team_name"] if team else "Unknown"
                
                col_pos, col_team, col_delete = st.columns([1, 3, 1])
                with col_pos:
                    st.write(f"**{tip['predicted_position']}.**")
                with col_team:
                    st.write(team_name)
                with col_delete:
                    if st.button("🗑️", key=f"delete_{tip['id']}"):
                        if delete_top6_tip(tip["id"]):
                            st.success("Gelöscht!")
                            time.sleep(1)
                            st.rerun()
        else:
            st.info("Noch keine Tipps gespeichert.")
    
    with col2:
        st.subheader("Neuen Tipp hinzufügen")
        
        # Freie Positionen
        tipped_positions = [t["predicted_position"] for t in player_tips]
        free_positions = [p for p in range(1, 7) if p not in tipped_positions]
        
        if free_positions:
            selected_position = st.selectbox("Platz wählen", free_positions)
            
            # Bereits getippte Teams ausblenden
            tipped_team_ids = [t["team_id"] for t in player_tips]
            available_teams = sorted([t for t in teams if t["id"] not in tipped_team_ids], 
                                   key=lambda x: x["team_name"])
            
            team_options = [f"{t['team_name']}" for t in available_teams]
            selected_team_name = st.selectbox("Team wählen", team_options)
            selected_team = next(t for t in available_teams if t["team_name"] == selected_team_name)
            
            if st.button("✅ Tipp speichern", use_container_width=True):
                if save_top6_tip(season_id, selected_player["id"], selected_team["id"], selected_position):
                    st.success(f"✅ Platz {selected_position}: {selected_team['team_name']}")
                    time.sleep(1)
                    st.rerun()
        else:
            st.success("🎉 Alle 6 Plätze gefüllt!")

# ============================================
# TAB 3: BUNDESLIGA-TABELLE (Live)
# ============================================

with tab3:
    st.header("🏆 Aktuelle Bundesliga-Tabelle (2026/27)")
    
    if st.button("🔄 Aktualisieren"):
        st.rerun()
    
    table_data = get_bundesliga_table()
    
    if table_data:
        # DataFrame bauen
        table_df = pd.DataFrame([{
            "Platz": t.get("Tabellenplatz", "-"),
            "Team": t.get("TeamName", "Unknown"),
            "Sp.": t.get("Spiele", 0),
            "S": t.get("Siege", 0),
            "U": t.get("Unentschieden", 0),
            "N": t.get("Niederlagen", 0),
            "Tore": t.get("Torverhaeltnis", "0:0"),
            "Punkte": t.get("Punkte", 0)
        } for t in table_data])
        
        st.dataframe(table_df, use_container_width=True, hide_index=True)
        st.caption("📡 Daten von OpenLigaDB • 🔄 Live aktualisiert")
    else:
        st.error("⚠️ Konnte Tabelle nicht laden. Später nochmal versuchen.")
