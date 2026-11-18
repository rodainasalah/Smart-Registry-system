import psycopg2

conn = psycopg2.connect(
    dbname="postgres",
    user="postgres",
    password="123456",  # Replace with your actual password
    host="localhost"
)
cur = conn.cursor()

# Insert all Year 3 tracks and comprehensive courses into PostgreSQL
cur.execute("""
-- Clear out old courses or insert safely
INSERT INTO courses (course_code, course_name, weekly_hours, requires_lab, professor_id) VALUES 
-- Common Core Year 3
('PRJ301', 'Graduation Project', 2, FALSE, 3),
('DAT301', 'Data Wrangling & Visualization', 3, TRUE, 4),
('ENG301', 'English Int. Career Prep', 2, FALSE, 5),
('FRE301', 'French 5', 2, FALSE, 6),

-- Track 1: AI & Data Science
('AI301', 'Unsupervised Machine Learning', 3, TRUE, 1),
('AI302', 'Statistical ML & Inference', 3, TRUE, 1),
('AI303', 'Deep Neural Networks', 3, TRUE, 2),
('AI304', 'NLP & Transformers', 3, TRUE, 2),

-- Track 2: FinTech & Blockchain
('FIN301', 'Cloud Computing Strategies in FinTech', 3, TRUE, 1),
('FIN302', 'Blockchain Technology', 3, TRUE, 1),
('FIN303', 'E-Business & Payment Systems', 3, FALSE, 2),
('FIN304', 'AI Applications in Financial Services', 3, TRUE, 2),

-- Track 3: Media Informatics & Mixed Reality
('MED301', 'Digital Media and Interactive Systems', 3, TRUE, 1),
('MED302', 'Advanced Full-Stack Web Development', 3, TRUE, 1),
('MED303', 'Human Computer Interaction', 3, FALSE, 2),
('MED304', 'Game Design and Development', 3, TRUE, 2),

-- Year 2 Retakes
('MGT406', 'Agile, Scrum & DevOps', 3, FALSE, 1),
('DAT404', 'Big Data Analysis', 3, TRUE, 4),
('ENG201', 'Year 2 English', 2, FALSE, 5),
('MGT305', 'Supply Chain Management', 3, FALSE, 1),
('FRE201', 'French 3', 2, FALSE, 6),
('VR402', 'Augmented & Virtual Reality', 3, TRUE, 2)
ON CONFLICT DO NOTHING;
""")

conn.commit()
cur.close()
conn.close()
print("All Year 3 tracks and courses successfully added to the database!")