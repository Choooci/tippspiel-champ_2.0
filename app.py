import json
import random
from typing import Any

import pandas as pd
import requests
import streamlit as st
from supabase import Client, create_client


# ============================================================
# KONFIGURATION
# ============================================================

st.set_page_config(
    page_title="⚽ Bundesliga Tippspiel",
    page_icon="⚽",
    layout="wide",
)

SUPABASE_URL = st.secrets["supabase_url"]
SUPABASE_KEY = st.secrets["supabase_key"]
ADMIN_USER = st.secrets.get("admin_user", "Choci")

AKTUELLE_SAISON = "2026-27"
AKTUELLES_BUNDESLIGA_JAHR = 2026

ANZAHL_SPIELER = 4
PICKS_PRO_SPIELER = 4
ANZAHL_PICKS = ANZAHL_SPIELER * PICKS_PRO_SPIELER

# Gewünschte Reihenfolge:
# 1 2 3 4 4 3 2 1 1 2 3 4 4 3 2 1
SNAKE_REIHENFOLGE = [
    0, 1, 2, 3,
    3, 2, 1, 0,
    0, 1, 2, 3,
    3, 2, 1, 0,
]

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)


# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def daten_oder_leere_liste(response: Any) -> list[dict]:
    """Gibt die Daten einer Supabase-Antwort als Liste zurück."""
    if response is None or not response.data:
        return []

    if isinstance(response.data, list):
        return response.data

    return [response.data]


def spieler_name(
    players: list[dict],
    player_id: int | None,
) -> str:
    """Ermittelt den Namen eines Spielers anhand seiner ID."""
    player = next(
        (
            item
            for item in players
            if item.get("id") == player_id
        ),
        None,
    )

    return player.get("name", "Unbekannt") if player else "Unbekannt"


def team_name(
    teams: list[dict],
    team_id: int | None,
) -> str:
    """Ermittelt den Teamnamen anhand seiner ID."""
    team = next(
        (
            item
            for item in teams
            if item.get("id") == team_id
        ),
        None,
    )

    return team.get("team_name", "Unbekannt") if team else "Unbekannt"


def auslosung_zu_draft_order(
    sitzreihenfolge: list[int],
) -> list[int]:
    """Erstellt aus vier Spielern die vollständige Reihenfolge."""
    if len(sitzreihenfolge) != ANZAHL_SPIELER:
        raise ValueError(
            f"Es werden genau {ANZAHL_SPIELER} Spieler benötigt."
        )

    return [
        sitzreihenfolge[index]
        for index in SNAKE_REIHENFOLGE
    ]


# ============================================================
# SUPABASE: SAISON
# ============================================================

def get_or_create_season(
    season_name: str,
) -> dict:
    """Lädt eine Saison oder legt sie an."""
    response = (
        supabase
        .table("seasons")
        .select("*")
        .eq("name", season_name)
        .limit(1)
        .execute()
    )

    if response.data:
        season = response.data[0]

        # Fehlende Statuswerte nachträglich korrigieren
        if not season.get("draft_status"):
            (
                supabase
                .table("seasons")
                .update({
                    "draft_status": "waiting",
                    "is_active": True,
                })
                .eq("id", season["id"])
                .execute()
            )

            season["draft_status"] = "waiting"

        return season

    response = (
        supabase
        .table("seasons")
        .insert({
            "name": season_name,
            "is_active": True,
            "draft_order": None,
            "draft_status": "waiting",
        })
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Die Saison konnte nicht angelegt werden."
        )

    return response.data[0]


def get_draft_status(season_id: int) -> str:
    """Lädt den aktuellen Draftstatus."""
    response = (
        supabase
        .table("seasons")
        .select("draft_status")
        .eq("id", season_id)
        .limit(1)
        .execute()
    )

    if response.data:
        return response.data[0].get(
            "draft_status",
            "waiting",
        )

    return "waiting"


def update_draft_status(
    season_id: int,
    status: str,
) -> None:
    """Aktualisiert den Draftstatus."""
    (
        supabase
        .table("seasons")
        .update({
            "draft_status": status,
        })
        .eq("id", season_id)
        .execute()
    )


# ============================================================
# SUPABASE: SPIELER
# ============================================================

def get_players() -> list[dict]:
    """Lädt alle Spieler."""
    response = (
        supabase
        .table("players")
        .select("*")
        .order("id")
        .execute()
    )

    return daten_oder_leere_liste(response)


# ============================================================
# SUPABASE: TEAMS
# ============================================================

def get_teams_for_season(
    season_id: int,
) -> list[dict]:
    """Lädt alle Teams der aktuellen Saison."""
    response = (
        supabase
        .table("teams")
        .select("*")
        .eq("season_id", season_id)
        .order("team_name")
        .execute()
    )

    return daten_oder_leere_liste(response)


# ============================================================
# SUPABASE: DRAFT-REIHENFOLGE
# ============================================================

def get_draft_order(
    season_id: int,
) -> list[dict]:
    """Lädt die Draftreihenfolge."""
    response = (
        supabase
        .table("draft_order")
        .select("*")
        .eq("season_id", season_id)
        .order("position")
        .execute()
    )

    return daten_oder_leere_liste(response)


def save_draft_order(
    season_id: int,
    sitzreihenfolge: list[int],
) -> None:
    """
    Speichert die Auslosung und erzeugt daraus 16 Picks.
    """

    if len(sitzreihenfolge) != ANZAHL_SPIELER:
        raise ValueError(
            f"Es müssen genau {ANZAHL_SPIELER} Spieler "
            f"ausgelost werden."
        )

    if len(set(sitzreihenfolge)) != ANZAHL_SPIELER:
        raise ValueError(
            "Jeder Spieler darf nur einmal ausgelost werden."
        )

    komplette_reihenfolge = auslosung_zu_draft_order(
        sitzreihenfolge
    )

    # Alte Reihenfolge löschen
    (
        supabase
        .table("draft_order")
        .delete()
        .eq("season_id", season_id)
        .execute()
    )

    # Neue Reihenfolge speichern
    rows = [
        {
            "season_id": season_id,
            "player_id": player_id,
            "position": position,
        }
        for position, player_id in enumerate(
            komplette_reihenfolge,
            start=1,
        )
    ]

    response = (
        supabase
        .table("draft_order")
        .insert(rows)
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Die Draftreihenfolge konnte nicht gespeichert werden."
        )

    # Nur die vier Sitzplätze in seasons speichern
    (
        supabase
        .table("seasons")
        .update({
            "draft_order": json.dumps(sitzreihenfolge),
            "draft_status": "drawing",
        })
        .eq("id", season_id)
        .execute()
    )


def reset_draft_order(
    season_id: int,
) -> None:
    """Löscht die Draftreihenfolge."""
    (
        supabase
        .table("draft_order")
        .delete()
        .eq("season_id", season_id)
        .execute()
    )

    (
        supabase
        .table("seasons")
        .update({
            "draft_order": None,
            "draft_status": "waiting",
        })
        .eq("id", season_id)
        .execute()
    )


# ============================================================
# SUPABASE: PICKS
# ============================================================

def get_draft_picks(
    season_id: int,
) -> list[dict]:
    """Lädt alle bereits gespeicherten Picks."""
    response = (
        supabase
        .table("draft_picks")
        .select("*")
        .eq("season_id", season_id)
        .order("pick_order")
        .execute()
    )

    return daten_oder_leere_liste(response)


def save_draft_pick(
    season_id: int,
    player_id: int,
    team_id: int,
    pick_order: int,
) -> None:
    """Speichert einen Pick."""
    if pick_order < 1 or pick_order > ANZAHL_PICKS:
        raise ValueError("Ungültige Picknummer.")

    vorhandene_picks = get_draft_picks(season_id)

    if any(
        pick["pick_order"] == pick_order
        for pick in vorhandene_picks
    ):
        raise ValueError(
            "Dieser Pick wurde bereits gespeichert."
        )

    if any(
        pick["team_id"] == team_id
        for pick in vorhandene_picks
    ):
        raise ValueError(
            "Dieses Team wurde bereits gepickt."
        )

    pick = {
        "season_id": season_id,
        "player_id": player_id,
        "team_id": team_id,
        "pick_order": pick_order,
    }

    response = (
        supabase
        .table("draft_picks")
        .insert(pick)
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Der Draftpick konnte nicht gespeichert werden."
        )

    # Speicherung für spätere Auswertungen
    (
        supabase
        .table("player_picks")
        .upsert(
            pick,
            on_conflict="season_id,player_id,team_id",
        )
        .execute()
    )


def delete_all_draft_picks(
    season_id: int,
) -> None:
    """Löscht alle Picks der Saison."""
    (
        supabase
        .table("draft_picks")
        .delete()
        .eq("season_id", season_id)
        .execute()
    )

    (
        supabase
        .table("player_picks")
        .delete()
        .eq("season_id", season_id)
        .execute()
    )


# ============================================================
# OPENLIGADB
# ============================================================

def get_bundesliga_table(
    season_year: int,
) -> list[dict]:
    """Lädt die Bundesliga-Tabelle."""
    url = (
        "https://www.openligadb.de/api/"
        f"getbltable/bl1/{season_year}"
    )

    try:
        response = requests.get(
            url,
            timeout=10,
        )
        response.raise_for_status()

        data = response.json()

        return data if isinstance(data, list) else []

    except (
        requests.RequestException,
        ValueError,
    ):
        return []


# ============================================================
# AUSWERTUNG
# ============================================================

def teamdaten_aus_api(
    team_display_name: str,
    table_data: list[dict],
) -> tuple[int, int]:
    """Findet Punkte und Spiele eines Teams."""
    suchname = team_display_name.lower().strip()

    for row in table_data:
        api_name = str(
            row.get("teamName", "")
        ).lower().strip()

        if (
            suchname in api_name
            or api_name in suchname
        ):
            return (
                int(row.get("points", 0)),
                int(row.get("matches", 0)),
            )

    return 0, 0


def berechne_punkte(
    picks: list[dict],
    players: list[dict],
    teams: list[dict],
    table_data: list[dict],
) -> tuple[pd.DataFrame, dict]:
    """Berechnet die Punkte pro Spieler."""
    ergebnisse = {}

    for player in players:
        player_id = player["id"]
        name = player["name"]

        eigene_picks = [
            pick
            for pick in picks
            if pick["player_id"] == player_id
        ]

        team_ergebnisse = []
        gesamtpunkte = 0
        gesamtspiele = 0

        for pick in eigene_picks:
            team = next(
                (
                    item
                    for item in teams
                    if item["id"] == pick["team_id"]
                ),
                None,
            )

            if not team:
                continue

            team_display_name = team["team_name"]

            punkte, spiele = teamdaten_aus_api(
                team_display_name,
                table_data,
            )

            gesamtpunkte += punkte
            gesamtspiele += spiele

            team_ergebnisse.append({
                "Team": team_display_name,
                "Punkte": punkte,
                "Spiele": spiele,
            })

        ergebnisse[name] = {
            "Punkte": gesamtpunkte,
            "Spiele": gesamtspiele,
            "Teams": team_ergebnisse,
        }

    rangliste = pd.DataFrame([
        {
            "Name": name,
            "Punkte": daten["Punkte"],
            "Spiele": daten["Spiele"],
        }
        for name, daten in ergebnisse.items()
    ])

    if not rangliste.empty:
        rangliste = (
            rangliste
            .sort_values(
                by=["Punkte", "Spiele"],
                ascending=[False, False],
            )
            .reset_index(drop=True)
        )

        rangliste.insert(
            0,
            "Platz",
            range(1, len(rangliste) + 1),
        )

    return rangliste, ergebnisse


# ============================================================
# DARSTELLUNG
# ============================================================

def zeige_draft_reihenfolge(
    draft_order: list[dict],
    players: list[dict],
    current_pick: int,
) -> None:
    """Zeigt die 16 Draftpositionen."""
    st.subheader("🎲 Draft-Reihenfolge")

    if not draft_order:
        st.info(
            "Die Draftreihenfolge wurde noch nicht ausgelost."
        )
        return

    rows = []

    for row in draft_order:
        position = row["position"]

        if position < current_pick:
            status = "✅ erledigt"
        elif position == current_pick:
            status = "▶️ aktuell"
        else:
            status = "⏳ offen"

        rows.append({
            "Pick": position,
            "Spieler": spieler_name(
                players,
                row["player_id"],
            ),
            "Status": status,
        })

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )


def zeige_finale_picks(
    picks: list[dict],
    players: list[dict],
    teams: list[dict],
) -> None:
    """Zeigt die Teams pro Spieler."""
    st.subheader("🏆 Teamverteilung")

    for player in players:
        eigene_picks = [
            pick
            for pick in picks
            if pick["player_id"] == player["id"]
        ]

        if not eigene_picks:
            continue

        st.markdown(f"### {player['name']}")

        rows = []

        for pick in eigene_picks:
            team = next(
                (
                    item
                    for item in teams
                    if item["id"] == pick["team_id"]
                ),
                None,
            )

            if team:
                rows.append({
                    "Pick": pick["pick_order"],
                    "Team": team["team_name"],
                })

        if rows:
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )


def zeige_verfuegbare_teams(
    teams: list[dict],
    picks: list[dict],
) -> None:
    """Zeigt noch verfügbare Teams."""
    gepickte_team_ids = {
        pick["team_id"]
        for pick in picks
    }

    verfuegbare_teams = [
        team
        for team in teams
        if team["id"] not in gepickte_team_ids
    ]

    st.subheader(
        f"⚽ Verfügbare Teams "
        f"({len(verfuegbare_teams)})"
    )

    if not verfuegbare_teams:
        st.info("Keine Teams mehr verfügbar.")
        return

    columns = st.columns(6)

    for index, team in enumerate(verfuegbare_teams):
        with columns[index % 6]:
            logo_url = team.get("logo_url")

            if (
                logo_url
                and str(logo_url).startswith("http")
            ):
                st.image(
                    logo_url,
                    width=60,
                )

            st.caption(team["team_name"])


# ============================================================
# APP-START
# ============================================================

st.title("⚽ Bundesliga Tippspiel")

try:
    season = get_or_create_season(
        AKTUELLE_SAISON
    )

    season_id = season["id"]
    players = get_players()
    teams = get_teams_for_season(season_id)
    draft_status = get_draft_status(season_id)

except Exception as error:
    st.error(
        f"Die Daten konnten nicht geladen werden: {error}"
    )
    st.stop()


if len(players) != ANZAHL_SPIELER:
    st.warning(
        f"Es müssen genau {ANZAHL_SPIELER} Spieler "
        f"vorhanden sein. Gefunden: {len(players)}."
    )

if not players:
    st.error(
        "Keine Spieler in Supabase gefunden."
    )
    st.stop()


# ============================================================
# PROFILAUSWAHL
# ============================================================

st.sidebar.header("👤 Profil")

player_names = [
    player["name"]
    for player in players
]

if ADMIN_USER not in player_names:
    player_names.append(ADMIN_USER)

current_player_name = st.sidebar.selectbox(
    "Wer bist Du?",
    player_names,
)

is_admin = (
    current_player_name == ADMIN_USER
)

if is_admin:
    st.sidebar.success(
        "✅ Adminmodus aktiv"
    )
else:
    st.sidebar.info(
        f"👀 Angemeldet als {current_player_name}"
    )

st.sidebar.divider()
st.sidebar.write(
    f"**Saison:** {AKTUELLE_SAISON}"
)
st.sidebar.write(
    f"**Draftstatus:** `{draft_status}`"
)

tab_draft, tab_overview, tab_admin = st.tabs([
    "🎲 Draft",
    "📊 Saisonübersicht",
    "⚙️ Administration",
])


# ============================================================
# TAB: DRAFT
# ============================================================

with tab_draft:
    draft_order = get_draft_order(season_id)
    draft_picks = get_draft_picks(season_id)

    current_pick_number = len(draft_picks) + 1

    if draft_status == "waiting":
        st.subheader("🎲 Auslosung")

        st.info(
            "Zuerst wird ausgelost, wer auf Position 1 bis 4 "
            "sitzt. Danach beginnt der Team-Draft."
        )

        if is_admin:
            if st.button(
                "🎰 Sitzreihenfolge auslosen",
                type="primary",
            ):
                try:
                    shuffled_players = players.copy()
                    random.shuffle(shuffled_players)

                    sitzreihenfolge = [
                        player["id"]
                        for player in shuffled_players
                    ]

                    save_draft_order(
                        season_id,
                        sitzreihenfolge,
                    )

                    st.success(
                        "Die Draftreihenfolge wurde ausgelost."
                    )
                    st.rerun()

                except Exception as error:
                    st.error(
                        "Die Auslosung konnte nicht gespeichert "
                        f"werden: {error}"
                    )
        else:
            st.info(
                "Warte, bis der Admin die Sitzreihenfolge auslost."
            )

    elif draft_status == "drawing":
        st.subheader("✅ Auslosung abgeschlossen")

        zeige_draft_reihenfolge(
            draft_order,
            players,
            current_pick_number,
        )

        if is_admin:
            st.warning(
                "Überprüfe die Reihenfolge und starte anschließend "
                "den Team-Draft."
            )

            if st.button(
                "➡️ Team-Draft starten",
                type="primary",
            ):
                try:
                    update_draft_status(
                        season_id,
                        "team_draft",
                    )
                    st.rerun()

                except Exception as error:
                    st.error(
                        f"Der Draft konnte nicht gestartet werden: {error}"
                    )
        else:
            st.info(
                "Warte, bis der Admin den Team-Draft startet."
            )

    elif draft_status == "team_draft":
        st.subheader("🏆 Team-Draft")

        if not draft_order:
            st.error(
                "Keine Draftreihenfolge vorhanden."
            )
            st.stop()

        zeige_draft_reihenfolge(
            draft_order,
            players,
            current_pick_number,
        )

        if current_pick_number <= ANZAHL_PICKS:
            current_order_row = next(
                (
                    row
                    for row in draft_order
                    if row["position"] == current_pick_number
                ),
                None,
            )

            if not current_order_row:
                st.error(
                    "Die aktuelle Draftposition wurde nicht gefunden."
                )
                st.stop()

            current_player_id = current_order_row["player_id"]
            current_player = spieler_name(
                players,
                current_player_id,
            )

            st.divider()

            st.info(
                f"🎯 **Pick {current_pick_number}: "
                f"{current_player} ist an der Reihe.**"
            )

            zeige_verfuegbare_teams(
                teams,
                draft_picks,
            )

            if current_player_name == current_player:
                gepickte_team_ids = {
                    pick["team_id"]
                    for pick in draft_picks
                }

                verfuegbare_teams = [
                    team
                    for team in teams
                    if team["id"] not in gepickte_team_ids
                ]

                if not verfuegbare_teams:
                    st.error(
                        "Keine verfügbaren Teams mehr vorhanden."
                    )
                else:
                    team_options = {
                        team["id"]: team["team_name"]
                        for team in verfuegbare_teams
                    }

                    selected_team_id = st.selectbox(
                        "Wähle Dein Team:",
                        options=list(team_options.keys()),
                        format_func=lambda team_id: (
                            team_options[team_id]
                        ),
                        key=f"team_{current_pick_number}",
                    )

                    if st.button(
                        "✅ Team picken",
                        type="primary",
                    ):
                        try:
                            save_draft_pick(
                                season_id=season_id,
                                player_id=current_player_id,
                                team_id=selected_team_id,
                                pick_order=current_pick_number,
                            )

                            if current_pick_number == ANZAHL_PICKS:
                                update_draft_status(
                                    season_id,
                                    "completed",
                                )

                            st.success(
                                f"{current_player} hat "
                                f"{team_options[selected_team_id]} "
                                "gepickt."
                            )
                            st.rerun()

                        except Exception as error:
                            st.error(
                                f"Der Pick konnte nicht gespeichert "
                                f"werden: {error}"
                            )
            else:
                st.info(
                    f"Warte auf {current_player}."
                )

    elif draft_status == "completed":
        st.success(
            "✅ Der Draft ist abgeschlossen."
        )

        zeige_finale_picks(
            draft_picks,
            players,
            teams,
        )


# ============================================================
# TAB: SAISONÜBERSICHT
# ============================================================

with tab_overview:
    st.subheader(
        f"📊 Bundesliga-Tabelle {AKTUELLE_SAISON}"
    )

    table_data = get_bundesliga_table(
        AKTUELLES_BUNDESLIGA_JAHR
    )

    if table_data:
        bundesliga_rows = []

        sortierte_tabelle = sorted(
            table_data,
            key=lambda item: int(
                item.get("points", 0)
            ),
            reverse=True,
        )

        for index, row in enumerate(
            sortierte_tabelle,
            start=1,
        ):
            bundesliga_rows.append({
                "Platz": index,
                "Team": row.get("teamName", ""),
                "Spiele": row.get("matches", 0),
                "Siege": row.get("won", 0),
                "Unentschieden": row.get("draw", 0),
                "Niederlagen": row.get("lost", 0),
                "Tore": (
                    f"{row.get('goalsFor', 0)}:"
                    f"{row.get('goalsAgainst', 0)}"
                ),
                "Punkte": row.get("points", 0),
            })

        st.dataframe(
            pd.DataFrame(bundesliga_rows),
            use_container_width=True,
            hide_index=True,
        )

        rangliste, einzel_ergebnisse = berechne_punkte(
            draft_picks,
            players,
            teams,
            table_data,
        )

        st.divider()
        st.subheader("🏆 Rangliste")

        if rangliste.empty:
            st.info(
                "Noch keine Picks vorhanden."
            )
        else:
            st.dataframe(
                rangliste,
                use_container_width=True,
                hide_index=True,
            )

            st.divider()
            st.subheader(
                "📋 Punkte der Einzelteams"
            )

            for name, result in einzel_ergebnisse.items():
                st.markdown(
                    f"### {name} – "
                    f"{result['Punkte']} Punkte"
                )

                if result["Teams"]:
                    st.dataframe(
                        pd.DataFrame(result["Teams"]),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info(
                        "Noch keine Teams vorhanden."
                    )

    else:
        st.warning(
            "Die Bundesliga-Tabelle konnte aktuell nicht "
            "geladen werden."
        )

    st.divider()
    st.subheader("🏆 Teamverteilung")

    if draft_picks:
        zeige_finale_picks(
            draft_picks,
            players,
            teams,
        )
    else:
        st.info(
            "Es wurden noch keine Teams gepickt."
        )


# ============================================================
# TAB: ADMINISTRATION
# ============================================================

with tab_admin:
    if not is_admin:
        st.error(
            "Dieser Bereich ist nur für den Admin sichtbar."
        )

    else:
        st.subheader("⚙️ Adminbereich")

        st.write(
            f"**Aktueller Status:** `{draft_status}`"
        )

        st.divider()
        st.markdown(
            "### 🔄 Draft zurücksetzen"
        )

        st.warning(
            "Dabei werden die Auslosung und alle Picks "
            "dieser Saison gelöscht."
        )

        if st.button(
            "🗑️ Draft vollständig zurücksetzen",
            type="secondary",
        ):
            try:
                delete_all_draft_picks(season_id)
                reset_draft_order(season_id)

                st.success(
                    "Der Draft wurde vollständig zurückgesetzt."
                )
                st.rerun()

            except Exception as error:
                st.error(
                    "Der Draft konnte nicht zurückgesetzt "
                    f"werden: {error}"
                )

        st.divider()
        st.markdown(
            "### ⚠️ Manuellen Status setzen"
        )

        status_options = [
            "waiting",
            "drawing",
            "team_draft",
            "completed",
        ]

        status_index = (
            status_options.index(draft_status)
            if draft_status in status_options
            else 0
        )

        selected_status = st.selectbox(
            "Neuer Status:",
            status_options,
            index=status_index,
        )

        if st.button(
            "Status speichern"
        ):
            try:
                update_draft_status(
                    season_id,
                    selected_status,
                )

                st.success(
                    "Status wurde gespeichert."
                )
                st.rerun()

            except Exception as error:
                st.error(
                    f"Status konnte nicht gespeichert werden: {error}"
                )

        st.divider()
        st.markdown("### 👥 Spieler")

        st.dataframe(
            pd.DataFrame(players),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.markdown(
            "### ⚽ Teams dieser Saison"
        )

        if teams:
            st.dataframe(
                pd.DataFrame(teams),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning(
                "Für diese Saison wurden noch keine Teams "
                "hinterlegt."
            )
