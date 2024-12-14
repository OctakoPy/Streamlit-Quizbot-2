import streamlit as st
import sqlite3
import random
import os

# Ensure a directory for user databases exists
USER_DB_DIR = ".user_databases"
os.makedirs(USER_DB_DIR, exist_ok=True)

class QuizApp:
    def __init__(self):
        # Generate or retrieve a unique user identifier
        if 'user_id' not in st.session_state:
            st.session_state.user_id = st.session_state.get('user_id', self.generate_user_id())
        
        # Database file path for this user
        self.db_path = os.path.join(USER_DB_DIR, f"{st.session_state.user_id}_questions.db")
        
        # Initialize the user's database if it doesn't exist
        self.initialize_user_database()
        
        # Initialize other session state variables
        self.initialize_session_state()

    def generate_user_id(self):
        """Generate a unique user identifier."""
        import uuid
        return str(uuid.uuid4())[:8]

    def initialize_session_state(self):
        """Initialize session state variables."""
        defaults = {
            'current_stage': 'menu',
            'quiz_type': None,
            'questions': [],
            'current_question_index': 0,
            'user_answers': [],
            'results': []
        }
        
        for key, default in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default

    def initialize_user_database(self):
        """Initialize the user's database with questions from the original database."""
        # Connect to the user's new database
        user_conn = sqlite3.connect(self.db_path)
        user_cursor = user_conn.cursor()
        
        try:
            # Create the questions table if it doesn't exist
            user_cursor.execute('''
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY,
                    question TEXT,
                    option1 TEXT,
                    option2 TEXT,
                    option3 TEXT,
                    option4 TEXT,
                    option5 TEXT,
                    answer TEXT,
                    has_asked BOOLEAN DEFAULT 0,
                    user_answered_correctly BOOLEAN DEFAULT 0
                )
            ''')
            
            # Check if the table is empty
            user_cursor.execute("SELECT COUNT(*) FROM questions")
            count = user_cursor.fetchone()[0]
            
            # If the table is empty, copy questions from the main database
            if count == 0:
                # Connect to the original database
                main_conn = sqlite3.connect("questions.db")
                main_cursor = main_conn.cursor()
                
                # Fetch all questions from the main database
                main_cursor.execute("SELECT * FROM questions")
                questions = main_cursor.fetchall()
                
                # Insert questions into the user's database
                user_cursor.executemany('''
                    INSERT INTO questions 
                    (id, question, option1, option2, option3, option4, option5, answer, has_asked, user_answered_correctly) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', questions)
                
                # Commit changes and close main database connection
                main_conn.commit()
                main_conn.close()
            
            # Commit changes to user database
            user_conn.commit()
        
        except sqlite3.Error as e:
            st.error(f"Database initialization error: {e}")
        
        finally:
            # Always close the user database connection
            user_conn.close()

    def connect_to_database(self):
        """Establish a connection to the user's SQLite database."""
        return sqlite3.connect(self.db_path)

    def get_random_questions(self, option):
        """
        Select 10 random questions based on the chosen option.
        
        Options:
        1 - Randomly select from all questions
        2 - Randomly select from untested questions
        3 - Randomly select from previously incorrect questions
        """
        conn = self.connect_to_database()
        cursor = conn.cursor()
        
        try:
            if option == 1:
                # Select 10 random questions from all questions
                cursor.execute("""
                    SELECT id, question, option1, option2, option3, option4, option5, answer 
                    FROM questions 
                    ORDER BY RANDOM() 
                    LIMIT 10
                """)
            elif option == 2:
                # Select 10 random questions that have not been asked before
                cursor.execute("""
                    SELECT id, question, option1, option2, option3, option4, option5, answer 
                    FROM questions 
                    WHERE has_asked = 0 
                    ORDER BY RANDOM() 
                    LIMIT 10
                """)
            elif option == 3:
                # Select 10 random questions that were previously answered incorrectly
                cursor.execute("""
                    SELECT id, question, option1, option2, option3, option4, option5, answer 
                    FROM questions 
                    WHERE has_asked = 1 AND user_answered_correctly = 0 
                    ORDER BY RANDOM() 
                    LIMIT 10
                """)
            
            questions = [dict(zip(['id', 'question', 'option1', 'option2', 'option3', 'option4', 'option5', 'answer'], row)) 
                         for row in cursor.fetchall()]
            return questions
        except sqlite3.Error as e:
            st.error(f"Database error: {e}")
            return []
        finally:
            conn.close()

    def reset_all_questions(self):
        """
        Reset all questions in the user's database:
        - Set has_asked to 0
        - Set user_answered_correctly to 0
        """
        conn = self.connect_to_database()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE questions 
                SET has_asked = 0, 
                    user_answered_correctly = 0
            """)
            conn.commit()
            st.toast("All questions have been reset successfully! 🔄")
        except sqlite3.Error as e:
            st.error(f"An error occurred while resetting questions: {e}")
        finally:
            conn.close()

    def start_quiz(self, quiz_type):
        """Start a new quiz with the specified type."""
        quiz_option_map = {
            "Random Quiz": 1,
            "Untested Questions Quiz": 2,
            "Incorrect Questions Quiz": 3
        }
        
        # Get questions
        questions = self.get_random_questions(quiz_option_map[quiz_type])
        
        if len(questions) < 10:
            st.error(f"Not enough questions available for {quiz_type}.")
            return
        
        # Shuffle options for each question
        for question in questions:
            options = [
                question['option1'], 
                question['option2'], 
                question['option3'], 
                question['option4'], 
                question['option5']
            ]
            random.shuffle(options)
            
            # Update question with shuffled options
            question['shuffled_options'] = options

        # Update session state
        st.session_state.questions = questions
        st.session_state.current_question_index = 0
        st.session_state.user_answers = []
        st.session_state.results = []
        st.session_state.current_stage = 'quiz'
        st.session_state.quiz_type = quiz_type
        st.rerun()

    def submit_answer(self, user_answer):
        """Process user's answer for the current question."""
        current_question = st.session_state.questions[st.session_state.current_question_index]
        
        # Store user's answer
        st.session_state.user_answers.append(user_answer)
        
        # Check if answer is correct
        is_correct = user_answer == current_question['answer']
        
        # Update results
        result = {
            'question': current_question['question'],
            'correct_answer': current_question['answer'],
            'user_answer': user_answer,
            'is_correct': is_correct
        }
        st.session_state.results.append(result)
        
        # Update database
        conn = self.connect_to_database()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE questions 
            SET has_asked = 1, 
                user_answered_correctly = ? 
            WHERE id = ?
        """, (is_correct, current_question['id']))
        conn.commit()
        conn.close()
        
        # Move to next question or end quiz
        st.session_state.current_question_index += 1
        
        # Check if quiz is complete
        if st.session_state.current_question_index >= len(st.session_state.questions):
            st.session_state.current_stage = 'results'
        
        st.rerun()

    def render_menu(self):
        """Render the main menu."""
        st.title("🧠 Quiz Master")
        
        # Display user ID (optional, for debugging)
        st.write(f"Your unique user ID: `{st.session_state.user_id}`")
        
        st.write("### Choose Your Quiz")
        
        quiz_types = [
            "Random Quiz", 
            "Untested Questions Quiz", 
            "Incorrect Questions Quiz"
        ]
        
        cols = st.columns(3)
        for i, quiz_type in enumerate(quiz_types):
            with cols[i]:
                if st.button(quiz_type, use_container_width=True):
                    self.start_quiz(quiz_type)
        
        # Reset Questions Button
        st.write("### Manage Questions")
        if st.button("Reset All Questions", type="secondary"):
            self.reset_all_questions()

    def render_quiz(self):
        """Render the current quiz question."""
        # Get current question
        current_question = st.session_state.questions[st.session_state.current_question_index]
        
        # Progress Indicator
        st.write(f"### Question {st.session_state.current_question_index + 1}/10")
        progress = (st.session_state.current_question_index + 1) / 10
        st.progress(progress)
        
        # Question Display
        st.write(f"## {current_question['question']}")
        
        # Answer Options
        user_answer = st.radio(
            "Select your answer:", 
            current_question['shuffled_options'], 
            key=f"question_{st.session_state.current_question_index}"
        )
        
        # Submit Button
        if st.button("Submit Answer"):
            self.submit_answer(user_answer)

    def render_results(self):
        """Display quiz results."""
        st.title("🏆 Quiz Results")
        
        # Calculate score
        score = sum(1 for result in st.session_state.results if result['is_correct'])
        
        # Score Display
        cols = st.columns([2,1,2])
        with cols[1]:
            st.metric("Your Score", f"{score}/10")
        
        # Detailed Results
        st.write("### Detailed Breakdown")
        
        for index, result in enumerate(st.session_state.results, 1):
            with st.expander(f"Question {index}", expanded=False):
                if result['is_correct']:
                    st.success("Correct ✅")
                else:
                    st.error("Incorrect ❌")
                
                st.write(f"**Question:** {result['question']}")
                st.write(f"**Your Answer:** {result['user_answer']}")
                st.write(f"**Correct Answer:** {result['correct_answer']}")
        
        # Return to Menu Button
        if st.button("Return to Menu"):
            st.session_state.current_stage = 'menu'
            st.rerun()

    def run(self):
        """Main application runner."""
        # Render based on current stage
        if st.session_state.current_stage == 'menu':
            self.render_menu()
        elif st.session_state.current_stage == 'quiz':
            self.render_quiz()
        elif st.session_state.current_stage == 'results':
            self.render_results()

def main():
    """Initialize and run the Quiz Master application."""
    app = QuizApp()
    app.run()

if __name__ == "__main__":
    main()