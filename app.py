"""Movie ranking app — pairwise comparisons with Glicko-2."""

from __future__ import annotations

import streamlit as st

from ranking.engine import (
    add_movie,
    apply_comparison,
    is_ranking_complete,
    progress_label,
    select_next_pair,
)
from ranking.storage import (
    csv_exists,
    csv_path,
    delete_session,
    init_or_resume_session,
    parse_movies_text,
    save_session,
)

st.set_page_config(page_title="Movie Rankings", page_icon="🎬", layout="centered")


def init_state() -> None:
    defaults = {
        "stage": "landing",
        "list_name": "",
        "movies_text": "",
        "session": None,
        "current_pair": None,
        "resumed": False,
        "add_movie_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_to_landing() -> None:
    st.session_state.stage = "landing"
    st.session_state.session = None
    st.session_state.current_pair = None
    st.session_state.resumed = False


def start_ranking(force_new: bool = False) -> None:
    list_name = st.session_state.list_name.strip()
    movies, duplicates = parse_movies_text(st.session_state.movies_text)

    if duplicates:
        st.warning(f"Removed duplicate entries: {', '.join(duplicates)}")

    if force_new and csv_exists(list_name):
        delete_session(list_name)

    session, resumed = init_or_resume_session(list_name, movies, force_new=force_new)

    if resumed:
        csv_movies = set(session.movies.keys())
        input_movies = set(movies)
        if csv_movies != input_movies:
            st.info(
                "Resuming saved ranking — using the movie list from your saved file."
            )
    elif movies:
        for name in movies:
            if name not in session.movies:
                from ranking.glicko import create_movie_rating

                session.movies[name] = create_movie_rating(name)

    st.session_state.session = session
    st.session_state.resumed = resumed
    st.session_state.current_pair = select_next_pair(session)
    st.session_state.stage = "ranking"


def render_landing() -> None:
    st.title("Movie Rankings")
    st.markdown(
        "Create a ranked list of your favorite movies by comparing them "
        "head-to-head. Add as many as you like — **10 or more** gives the best results."
    )

    st.session_state.list_name = st.text_input(
        "List name",
        value=st.session_state.list_name,
        placeholder="Phil's Favorite Movies",
    )

    st.session_state.movies_text = st.text_area(
        "Movies (one per line)",
        value=st.session_state.movies_text,
        height=220,
        placeholder="The Godfather\nCasablanca\nSpirited Away\n...",
    )

    movies, _ = parse_movies_text(st.session_state.movies_text)
    list_name = st.session_state.list_name.strip()
    can_start = bool(list_name) and len(movies) >= 2

    if list_name and csv_exists(list_name):
        st.info("Found existing ranking — continuing where you left off.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Continue Ranking", type="primary", disabled=not can_start):
                start_ranking(force_new=False)
                st.rerun()
        with col2:
            if st.button("Start Over", disabled=not can_start):
                start_ranking(force_new=True)
                st.rerun()
    else:
        if st.button("Start Ranking", type="primary", disabled=not can_start):
            start_ranking(force_new=False)
            st.rerun()

    if len(movies) == 1:
        st.caption("Add at least one more movie to start ranking.")
    elif len(movies) == 0 and st.session_state.movies_text.strip():
        st.caption("Add at least 2 movies to start ranking.")


def render_ranking() -> None:
    session = st.session_state.session
    if session is None:
        reset_to_landing()
        st.rerun()
        return

    st.title(session.list_name)
    st.caption(progress_label(session))

    if is_ranking_complete(session):
        st.session_state.stage = "results"
        st.rerun()
        return

    pair = st.session_state.current_pair
    if pair is None:
        pair = select_next_pair(session)
        st.session_state.current_pair = pair

    if pair is None:
        st.session_state.stage = "results"
        st.rerun()
        return

    movie_a, movie_b = pair
    st.subheader("Which movie is better?")

    col1, col2 = st.columns(2)
    with col1:
        if st.button(movie_a, use_container_width=True, type="primary"):
            apply_comparison(session, movie_a, movie_b)
            save_session(session)
            if is_ranking_complete(session):
                st.session_state.stage = "results"
                st.session_state.current_pair = None
            else:
                st.session_state.current_pair = select_next_pair(session)
            st.rerun()

    with col2:
        if st.button(movie_b, use_container_width=True, type="primary"):
            apply_comparison(session, movie_b, movie_a)
            save_session(session)
            if is_ranking_complete(session):
                st.session_state.stage = "results"
                st.session_state.current_pair = None
            else:
                st.session_state.current_pair = select_next_pair(session)
            st.rerun()

    st.divider()

    with st.expander("Forgot a movie?"):
        st.caption("Add a title you left off your initial list. It joins the ranking right away.")
        with st.form("add_movie_form", clear_on_submit=True):
            new_movie = st.text_input("Movie name", placeholder="The Matrix")
            if st.form_submit_button("Add to list"):
                error = add_movie(session, new_movie)
                if error:
                    st.session_state.add_movie_error = error
                else:
                    st.session_state.add_movie_error = None
                    st.session_state.movies_text = "\n".join(session.movies.keys())
                    save_session(session)
                    st.session_state.current_pair = select_next_pair(session)
                st.rerun()

    if st.session_state.get("add_movie_error"):
        st.warning(st.session_state.add_movie_error)

    if st.button("Finish early"):
        st.session_state.stage = "results"
        st.session_state.current_pair = None
        save_session(session)
        st.rerun()


def render_results() -> None:
    session = st.session_state.session
    if session is None:
        reset_to_landing()
        st.rerun()
        return

    st.title(f"Your Rankings: {session.list_name}")
    st.caption(progress_label(session))

    for rank, movie in enumerate(session.ordered_movies(), start=1):
        st.markdown(f"**{rank}.** {movie.movie}")

    with st.expander("Rating details"):
        for rank, movie in enumerate(session.ordered_movies(), start=1):
            st.write(
                f"{rank}. {movie.movie} — "
                f"rating: {movie.rating:.1f}, RD: {movie.rd:.1f}, "
                f"record: {movie.wins}W / {movie.losses}L"
            )

    path = save_session(session)
    st.download_button(
        label="Download CSV",
        data=path.read_bytes(),
        file_name=path.name,
        mime="text/csv",
    )

    if st.button("Start new list"):
        reset_to_landing()
        st.session_state.list_name = ""
        st.session_state.movies_text = ""
        st.rerun()


def main() -> None:
    init_state()

    stage = st.session_state.stage
    if stage == "landing":
        render_landing()
    elif stage == "ranking":
        render_ranking()
    elif stage == "results":
        render_results()
    else:
        reset_to_landing()
        st.rerun()


if __name__ == "__main__":
    main()
