import streamlit as st

from data import PROFESSORS, DAYS, SLOTS


st.set_page_config(
    page_title="Smart University Scheduler",
    page_icon="🎓",
    layout="wide"
)

st.title("🎓 Smart University Scheduling System")
st.caption("Phase 1 - Intelligent Academic Scheduling")


# -----------------------------------------
# SESSION STATE
# -----------------------------------------

if "professor_settings" not in st.session_state:
    st.session_state.professor_settings = {}


# -----------------------------------------
# TABS
# -----------------------------------------

tab1, tab2, tab3 = st.tabs([
    "👨‍🏫 Professor Availability",
    "📚 Academic Data",
    "⚙️ Generate Timetable"
])


# =========================================
# TAB 1 - PROFESSOR AVAILABILITY
# =========================================

with tab1:

    st.header("Professor Availability & Preferences")

    professor_names = {
        professor["name"]: professor["id"]
        for professor in PROFESSORS
    }

    selected_professor_name = st.selectbox(
        "Select Professor",
        list(professor_names.keys())
    )

    selected_professor_id = professor_names[
        selected_professor_name
    ]

    st.markdown("---")

    st.subheader("Weekly Availability")

    st.info(
        "Unavailable periods are HARD constraints. "
        "The scheduler will never assign the professor "
        "during these periods."
    )

    availability = {}

    for day in DAYS:

        st.markdown(f"### {day}")

        cols = st.columns(len(SLOTS))

        availability[day] = []

        for index, slot in enumerate(SLOTS):

            label = slot["start"]

            with cols[index]:

                available = st.checkbox(
                    label,
                    value=True,
                    key=(
                        f"available_"
                        f"{selected_professor_id}_"
                        f"{day}_"
                        f"{slot['id']}"
                    )
                )

                if available:
                    availability[day].append(
                        slot["id"]
                    )

    st.markdown("---")

    st.subheader("Preferred Teaching Times")

    st.info(
        "Preferred periods are SOFT constraints. "
        "The optimizer will try to use them, but may "
        "choose another available period if necessary."
    )

    preferences = {}

    for day in DAYS:

        st.markdown(f"### {day}")

        cols = st.columns(len(SLOTS))

        preferences[day] = []

        for index, slot in enumerate(SLOTS):

            with cols[index]:

                preferred = st.checkbox(
                    slot["start"],
                    value=False,
                    key=(
                        f"preferred_"
                        f"{selected_professor_id}_"
                        f"{day}_"
                        f"{slot['id']}"
                    )
                )

                if preferred:
                    preferences[day].append(
                        slot["id"]
                    )

    st.markdown("---")

    if st.button(
        "💾 Save Professor Settings",
        type="primary"
    ):

        unavailable = []
        preferred = []

        for day in DAYS:

            for slot in SLOTS:

                slot_id = slot["id"]

                if slot_id not in availability[day]:
                    unavailable.append(
                        (day, slot_id)
                    )

                if slot_id in preferences[day]:
                    preferred.append(
                        (day, slot_id)
                    )

        st.session_state.professor_settings[
            selected_professor_id
        ] = {
            "unavailable": unavailable,
            "preferred": preferred
        }

        st.success(
            f"Settings saved for "
            f"{selected_professor_name}"
        )


# =========================================
# TAB 2 - ACADEMIC DATA
# =========================================

with tab2:

    st.header("Academic Scheduling Data")

    st.subheader("Professors")

    for professor in PROFESSORS:
        st.write(
            f"• {professor['name']}"
        )

    st.markdown("---")

    st.info(
        "Courses, rooms, student groups and session "
        "requirements will be configurable here later."
    )


# =========================================
# TAB 3 - GENERATE
# =========================================

with tab3:

    st.header("AI Timetable Optimizer")

    st.write(
        "Professor settings currently saved:"
    )

    st.json(
        st.session_state.professor_settings
    )

    st.markdown("---")

    st.warning(
        "The Generate Timetable button will be connected "
        "to OR-Tools in the next step."
    )

    st.button(
        "🚀 Generate Optimized Timetable",
        type="primary",
        disabled=True
    )