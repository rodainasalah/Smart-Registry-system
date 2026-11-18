import streamlit as st
import psycopg2
import pandas as pd

def get_db_connection():
    return psycopg2.connect(
        dbname="postgres",
        user="postgres",
        password="123456",
        host="localhost"
    )

st.set_page_config(page_title="Smart University Registry", page_icon="🎓", layout="wide")

st.title("🎓 Smart University Registry & Scheduling System")
st.markdown("### Phase 1: Student Portal & Intelligent Scheduling Engine")

tab1, tab2 = st.tabs(["📅 View Timetable", "📝 Student Registration & Major Selection"])

with tab1:
    st.subheader("Interactive Academic Timetable")
    
    try:
        conn = get_db_connection()
        students_df = pd.read_sql("SELECT student_id, name, type FROM students;", conn)
        
        query = """
            SELECT 
                t.day_of_week,
                t.start_time,
                t.end_time,
                c.course_code,
                c.course_name,
                p.name AS professor,
                r.room_name,
                e.student_id
            FROM timetable t
            JOIN courses c ON t.course_id = c.course_id
            JOIN professors p ON c.professor_id = p.professor_id
            JOIN rooms r ON t.room_id = r.room_id
            JOIN enrollments e ON c.course_id = e.course_id;
        """
        schedule_df = pd.read_sql(query, conn)
        conn.close()
    except Exception as e:
        st.error(f"Database error: {e}")
        st.stop()

    view_mode = st.radio("View Mode:", ["All University Timetable", "Individual Student Schedule"], horizontal=True)

    if view_mode == "Individual Student Schedule":
        selected_student_name = st.selectbox("Select Student:", students_df['name'].tolist())
        selected_student_id = students_df[students_df['name'] == selected_student_name]['student_id'].values[0]
        display_df = schedule_df[schedule_df['student_id'] == selected_student_id]
        st.info(f"Showing registered schedule for: **{selected_student_name}**")
    else:
        display_df = schedule_df
        st.info("Showing master university schedule.")

    if not display_df.empty:
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Saturday']
        display_df['day_of_week'] = pd.Categorical(display_df['day_of_week'], categories=day_order, ordered=True)
        display_df = display_df.sort_values(by=['day_of_week', 'start_time'])
        
        clean_view = display_df[['day_of_week', 'start_time', 'end_time', 'course_code', 'course_name', 'professor', 'room_name']]
        clean_view.columns = ['Day', 'Start Time', 'End Time', 'Code', 'Course Name', 'Professor', 'Room']
        
        st.dataframe(clean_view, use_container_width=True, hide_index=True)
    else:
        st.warning("No scheduled classes found. Run `python scheduler.py` to generate room allocations!")

with tab2:
    st.subheader("Semester Course Registration & Major Portal")

    try:
        conn = get_db_connection()
        students_list = pd.read_sql("SELECT student_id, name FROM students;", conn)
        courses_list = pd.read_sql("SELECT course_id, course_code, course_name FROM courses;", conn).drop_duplicates(subset=['course_code'])
        conn.close()
    except Exception as e:
        st.error(f"Database error: {e}")
        st.stop()

    student_name = st.selectbox("Select Your Profile:", students_list['name'].tolist(), key="profile_select")
    student_id = students_list[students_list['name'] == student_name]['student_id'].values[0]

    st.markdown("---")
    
    major_track = st.selectbox("Choose Year 3 Track/Major:", [
        "AI & Data Science Track", 
        "FinTech & Blockchain Track", 
        "Media Informatics & Mixed Reality Track"
    ], key="major_select")

    st.markdown("---")
    st.markdown(f"#### Courses for {major_track}")
    
    selected_course_ids = []
    
    for index, row in courses_list.iterrows():
        c_id = row['course_id']
        c_code = row['course_code']
        c_name = row['course_name']
        
        is_core = c_code in ['PRJ301', 'DAT301', 'ENG301', 'FRE301']
        
        is_track_match = False
        if "AI" in major_track and c_code.startswith("AI"):
            is_track_match = True
        elif "FinTech" in major_track and c_code.startswith("FIN"):
            is_track_match = True
        elif "Media" in major_track and c_code.startswith("MED"):
            is_track_match = True
        
        is_retake = False
        if student_name == "Eyad Abdullah" and c_code in ['ENG201', 'MGT406', 'DAT404']:
            is_retake = True
        elif student_name == "Mahmoud Hesham Gharib" and c_code in ['MGT305', 'FRE201', 'VR402', 'ENG201', 'MGT406']:
            is_retake = True

        if is_core or is_track_match or is_retake:
            if st.checkbox(f"[{c_code}] {c_name}", value=True, key=f"reg_course_{c_id}"):
                selected_course_ids.append(c_id)

    st.markdown("---")
    if st.button("💾 Save Registration & Update Database", type="primary"):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            clean_student_id = int(student_id)
            
            cur.execute("DELETE FROM enrollments WHERE student_id = %s;", (clean_student_id,))
            for cid in selected_course_ids:
                cur.execute("INSERT INTO enrollments (student_id, course_id) VALUES (%s, %s);", (clean_student_id, int(cid)))
            
            conn.commit()
            cur.close()
            conn.close()
            st.success(f"Successfully updated registration for **{student_name}** under **{major_track}**! Run `python scheduler.py` in your terminal to update room timings.")
        except Exception as e:
            st.error(f"Error saving: {e}")