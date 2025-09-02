from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Database configuration
db_config = {
    'host': os.getenv("DB_HOST"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'database': os.getenv("DB_NAME")
}

# Helper function to connect to MySQL database
def connect_db():
    return mysql.connector.connect(**db_config)

# Route for the root URL - redirects to login page
@app.route('/')
def index():
    return redirect(url_for('login'))

# User login route - handles both GET (form display) and POST (form submission)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get login credentials from form data
        username = request.form['username']
        password = request.form['password']

        conn = connect_db()
        cursor = conn.cursor()
        
        # Check if user exists, get password and restriction status
        cursor.execute("SELECT userID, password, is_restricted FROM User WHERE username = %s", (username,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        # Validate user credentials and check restriction status
        if user and user[1] == password:
            # Check if user is restricted from logging in
            if user[2] == 1:  # is_restricted = TRUE
                flash("You are restricted and cannot log in.", "error")
                return render_template('login.html')
            
            # If credentials are valid and user is not restricted, set user ID in session
            session['user_id'] = user[0]
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials.", "error")

    return render_template('login.html')

# Logout route - clears session and redirects to login
@app.route('/logout')
def logout():
    session.clear()  # Clear all session data
    flash("You've been logged out.", "info")
    return redirect(url_for('login'))

# User signup route - handles both GET (form display) and POST (form submission)
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Fetch all cities for dropdown
    cursor.execute("SELECT city_code, city_name FROM City ORDER BY city_name")
    cities = cursor.fetchall()

    # Fetch all neighborhoods for dropdown
    cursor.execute("SELECT postal_code, area_name, city_code FROM Neighborhood ORDER BY area_name")
    neighborhoods = cursor.fetchall()

    if request.method == 'POST':
        # Get form data from POST request
        username = request.form['username']
        email = request.form['email']
        gender = request.form['gender']
        password = request.form['password']
        city_code = request.form.get('city')
        postal_code = request.form.get('neighborhood')

        try:
            # Insert new user into User table
            cursor.execute("""
                INSERT INTO User (username, email, gender, password, city_code, postal_code)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (username, email, gender, password, city_code, postal_code))
            conn.commit()
            flash('Signup successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            flash(f'Error: {err}', 'danger')
            
    cursor.close()
    conn.close()

    return render_template('signup.html', cities=cities, neighborhoods=neighborhoods, neighborhoods_json=neighborhoods)

# Dashboard route - main page after login
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Please log in", "error")
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)
    
    # Get current user's basic info
    cursor.execute("SELECT username, city_code FROM User WHERE userID = %s", (session['user_id'],))
    user = cursor.fetchone()

    # Get city name
    cursor.execute("SELECT city_name FROM City WHERE city_code = %s", (user['city_code'],))
    city = cursor.fetchone()['city_name'] if user['city_code'] else 'Unknown'

    # Check if user is admin
    cursor.execute("SELECT is_admin FROM User WHERE userID = %s", (session['user_id'],))
    is_admin = cursor.fetchone()['is_admin'] == 1

    cursor.close()
    conn.close()

    return render_template("dashboard.html", username=user['username'], city_name=city, is_admin=is_admin)

# Route for similar interests matches - redirects to city tab by default
@app.route('/users/match')
def similar_interests_root():
    return redirect(url_for('similar_interests', scope='city'))

# Route to find users with similar interests based on city or neighborhood
@app.route('/users/match/<scope>')
def similar_interests(scope):
    if 'user_id' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('login'))

    if scope not in ('city', 'neighborhood'):
        # Fallback to city tab if invalid scope is provided
        return redirect(url_for('similar_interests', scope='city'))

    user_id = session['user_id']

    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Get current user's location (city & neighborhood)
    cursor.execute("SELECT city_code, postal_code FROM User WHERE userID = %s", (user_id,))
    row = cursor.fetchone()
    user_city_code = row['city_code']
    user_postal = row['postal_code']

    # Get current user's interest IDs
    cursor.execute("SELECT interest_ID FROM User_Interest WHERE userID = %s", (user_id,))
    interest_ids = [r['interest_ID'] for r in cursor.fetchall()]

    if not interest_ids:
        cursor.close()
        conn.close()
        flash("You haven't selected any interests yet—add some to see matches.", "warning")
        return redirect(url_for('profile', user_id=user_id))

    # Dynamically build IN clause placeholders for interest IDs
    in_placeholders = ','.join(['%s'] * len(interest_ids))

    # Scope condition: city or neighborhood
    if scope == 'city':
        scope_condition = "u.city_code = %s"
        scope_value = user_city_code
    else:
        scope_condition = "u.postal_code = %s"
        scope_value = user_postal

    # Count total distinct users matching (exclude self + current friends)
    count_sql = f"""
        SELECT COUNT(*) AS total FROM (
            SELECT DISTINCT u.userID
            FROM User u
            JOIN User_Interest ui ON u.userID = ui.userID
            WHERE u.userID != %s
              AND {scope_condition}
              AND ui.interest_ID IN ({in_placeholders})
              AND u.userID NOT IN (
                  SELECT user2_ID FROM Friendship WHERE user1_ID = %s
                  UNION
                  SELECT user1_ID FROM Friendship WHERE user2_ID = %s
              )
        ) AS sub
    """
    cursor.execute(count_sql, (user_id, scope_value, *interest_ids, user_id, user_id))
    total_users = cursor.fetchone()['total']
    total_pages = (total_users + per_page - 1) // per_page

    # Fetch page of users with shared interest count (sorted by match count DESC)
    page_sql = f"""
        SELECT
            u.userID,
            u.username,
            u.email,
            COUNT(ui.interest_ID) AS shared_count
        FROM User u
        JOIN User_Interest ui ON u.userID = ui.userID
        WHERE u.userID != %s
          AND {scope_condition}
          AND ui.interest_ID IN ({in_placeholders})
          AND u.userID NOT IN (
              SELECT user2_ID FROM Friendship WHERE user1_ID = %s
              UNION
              SELECT user1_ID FROM Friendship WHERE user2_ID = %s
          )
        GROUP BY u.userID, u.username, u.email
        ORDER BY shared_count DESC, u.username ASC
        LIMIT %s OFFSET %s
    """
    cursor.execute(page_sql, (user_id, scope_value, *interest_ids, user_id, user_id, per_page, offset))
    users_page = cursor.fetchall()

    # Collect IDs on this page to fetch the actual shared interest names
    matches = []
    if users_page:
        page_user_ids = [u['userID'] for u in users_page]
        user_id_placeholders = ','.join(['%s'] * len(page_user_ids))

        interests_sql = f"""
            SELECT ui.userID, i.interest_name
            FROM User_Interest ui
            JOIN Interest i ON ui.interest_ID = i.interest_ID
            WHERE ui.userID IN ({user_id_placeholders})
              AND ui.interest_ID IN ({in_placeholders})
            ORDER BY i.interest_name
        """
        cursor.execute(interests_sql, (*page_user_ids, *interest_ids))
        interest_rows = cursor.fetchall()

        interest_map = {}
        for r in interest_rows:
            interest_map.setdefault(r['userID'], []).append(r['interest_name'])

        # Assemble final list
        for u in users_page:
            matches.append({
                'userID': u['userID'],
                'username': u['username'],
                'email': u['email'],
                'shared_interests': interest_map.get(u['userID'], []),
                'shared_count': u['shared_count']
            })

    # Friend request statuses involving the current user <-> page users
    if users_page:
        cursor.execute("""
            SELECT sender_id, receiver_id, status
            FROM FriendRequest
            WHERE (sender_id = %s AND receiver_id IN ({ids}))
               OR (receiver_id = %s AND sender_id IN ({ids}))
        """.format(ids=user_id_placeholders), (user_id, *page_user_ids, user_id, *page_user_ids))
        req_rows = cursor.fetchall()
    else:
        req_rows = []

    request_status = {}
    for r in req_rows:
        # If I sent it, track status keyed by the other user
        if r['sender_id'] == user_id:
            request_status[r['receiver_id']] = r['status']
        else:
            request_status[r['sender_id']] = r['status']

    cursor.close()
    conn.close()

    return render_template(
        "interest_matches_tabs.html",
        scope=scope,
        matches=matches,
        request_status=request_status,
        page=page,
        total_pages=total_pages
    )

# Route to send friend request
@app.route('/friend_request/send/<int:receiver_id>', methods=['POST'])
def send_friend_request(receiver_id):
    if 'user_id' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('login'))

    sender_id = session['user_id']

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Check if a pending friend request already exists from this user to the receiver
    cursor.execute("""
        SELECT 1 FROM FriendRequest
        WHERE sender_id = %s AND receiver_id = %s AND status = 'pending'
    """, (sender_id, receiver_id))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return redirect(request.referrer or url_for('similar_interests_root'))

    # Check if the users are already friends
    cursor.execute("""
        SELECT 1 FROM Friendship
        WHERE (user1_ID = %s AND user2_ID = %s) OR (user1_ID = %s AND user2_ID = %s)
    """, (sender_id, receiver_id, receiver_id, sender_id))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        flash("You are already friends.", "info")
        return redirect(request.referrer or url_for('similar_interests_root'))

    # Insert a new friend request into the FriendRequest table
    cursor.execute("""
        INSERT INTO FriendRequest (sender_id, receiver_id) VALUES (%s, %s)
    """, (sender_id, receiver_id))
    conn.commit()

    cursor.close()
    conn.close()
    
    return redirect(request.referrer or url_for('similar_interests_root'))

# Route to cancel friend request
@app.route('/friend_request/cancel/<int:receiver_id>', methods=['POST'])
def cancel_friend_request(receiver_id):
    if 'user_id' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('login'))

    user_id = session['user_id']

    conn = connect_db()
    cursor = conn.cursor()

    # Delete the pending friend request sent by the user
    cursor.execute("""
        DELETE FROM FriendRequest
        WHERE sender_id = %s AND receiver_id = %s AND status = 'pending'
    """, (user_id, receiver_id))

    conn.commit()
    cursor.close()
    conn.close()
    return redirect(request.referrer or url_for('similar_interests_root'))

# Route to manage incoming friend requests
@app.route('/friend_request/manage')
def manage_friend_requests():
    if 'user_id' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('login'))

    # Pagination setup
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Count total pending requests
    cursor.execute("""
        SELECT COUNT(*) as total
        FROM FriendRequest fr
        WHERE fr.receiver_id = %s AND fr.status = 'pending'
    """, (session['user_id'],))
    total_requests = cursor.fetchone()['total']
    total_pages = (total_requests + per_page - 1) // per_page

    # Get paginated list of pending requests
    cursor.execute("""
        SELECT fr.request_id, u.userID, u.username, u.email
        FROM FriendRequest fr
        JOIN User u ON fr.sender_id = u.userID
        WHERE fr.receiver_id = %s AND fr.status = 'pending'
        LIMIT %s OFFSET %s
    """, (session['user_id'], per_page, offset))

    requests = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        'manage_requests.html',
        requests=requests,
        page=page,
        total_pages=total_pages
    )

# Route to accept friend request
@app.route('/friend_request/accept/<int:request_id>', methods=['POST'])
def accept_friend_request(request_id):
    if 'user_id' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor()

    # Get sender and receiver IDs from request
    cursor.execute("""
        SELECT sender_id, receiver_id FROM FriendRequest 
        WHERE request_id = %s AND status = 'pending'
    """, (request_id,))
    result = cursor.fetchone()

    if result:
        sender_id, receiver_id = result
        # Update request status to 'accepted'
        cursor.execute("""
            UPDATE FriendRequest SET status = 'accepted' WHERE request_id = %s
        """, (request_id,))
        # Create friendship record
        cursor.execute("""
            INSERT INTO Friendship (user1_ID, user2_ID) VALUES (%s, %s)
        """, (sender_id, receiver_id))
        conn.commit()

    cursor.close()
    conn.close()
    return redirect(url_for('manage_friend_requests'))

# Route to decline friend request
@app.route('/friend_request/decline/<int:request_id>', methods=['POST'])
def decline_friend_request(request_id):
    if 'user_id' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor()

    # Update request status to 'declined'
    cursor.execute("""
        UPDATE FriendRequest SET status = 'declined' 
        WHERE request_id = %s AND receiver_id = %s
    """, (request_id, session['user_id']))
    conn.commit()

    cursor.close()
    conn.close()
    return redirect(url_for('manage_friend_requests'))

# Route to view friends list
@app.route('/friends')
def view_friends():
    if 'user_id' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('login'))

    user_id = session['user_id']

    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Count total friends
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM Friendship f
        JOIN User u ON (
            (f.user1_ID = u.userID AND f.user2_ID = %s) OR 
            (f.user2_ID = u.userID AND f.user1_ID = %s)
        )
    """, (user_id, user_id))
    total_friends = cursor.fetchone()['total']
    total_pages = (total_friends + per_page - 1) // per_page

    # Fetch paginated friends list
    cursor.execute("""
        SELECT u.userID, u.username, u.email
        FROM Friendship f
        JOIN User u ON (
            (f.user1_ID = u.userID AND f.user2_ID = %s) OR 
            (f.user2_ID = u.userID AND f.user1_ID = %s)
        )
        LIMIT %s OFFSET %s
    """, (user_id, user_id, per_page, offset))

    friends = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('friend_list.html', friends=friends, page=page, total_pages=total_pages)

# Route to remove a friend
@app.route('/friend/remove/<int:friend_id>', methods=['POST'])
def remove_friend(friend_id):
    if 'user_id' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('login'))

    user_id = session['user_id']

    conn = connect_db()
    cursor = conn.cursor()

    # Delete friendship record
    cursor.execute("""
        DELETE FROM Friendship 
        WHERE (user1_ID = %s AND user2_ID = %s)
           OR (user1_ID = %s AND user2_ID = %s)
    """, (user_id, friend_id, friend_id, user_id))

    # Also delete any accepted friend requests between these users
    cursor.execute("""
        DELETE FROM FriendRequest
        WHERE ((sender_id = %s AND receiver_id = %s) OR
               (sender_id = %s AND receiver_id = %s))
          AND status = 'accepted'
    """, (user_id, friend_id, friend_id, user_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('view_friends'))

# Route for chat with a friend
@app.route('/chat/<int:friend_id>', methods=['GET', 'POST'])
def chat(friend_id):
    if 'user_id' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('login'))

    user_id = session['user_id']

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Verify that friendship exists between current user and friend
    # Check both directions since friendship can be stored either way
    cursor.execute("""
        SELECT * FROM Friendship 
        WHERE (user1_ID = %s AND user2_ID = %s)
           OR (user1_ID = %s AND user2_ID = %s)
    """, (user_id, friend_id, friend_id, user_id))
    friendship = cursor.fetchone()

    # If no friendship exists, redirect to friends list
    if not friendship:
        return redirect(url_for('view_friends'))

    # Handle POST request when user sends a new message
    if request.method == 'POST':
        # Get message content from form
        content = request.form['message']
        
        # Insert new message into database
        cursor.execute("""
            INSERT INTO Message (sender_ID, receiver_ID, content)
            VALUES (%s, %s, %s)
        """, (user_id, friend_id, content))
        conn.commit()

    # Fetch all messages between current user and friend
    # Join with User table to get sender's username
    cursor.execute("""
        SELECT m.*, u.username AS sender_name
        FROM Message m
        JOIN User u ON m.sender_ID = u.userID
        WHERE (sender_ID = %s AND receiver_ID = %s)
           OR (sender_ID = %s AND receiver_ID = %s)
        ORDER BY timestamp ASC
    """, (user_id, friend_id, friend_id, user_id))
    messages = cursor.fetchall()

    # Get friend's username for display
    cursor.execute("SELECT username FROM User WHERE userID = %s", (friend_id,))
    friend_name = cursor.fetchone()['username']

    cursor.close()
    conn.close()

    return render_template("chat.html", 
                         messages=messages, 
                         friend_name=friend_name, 
                         friend_id=friend_id,
                         current_user_id=user_id)  # Pass current user ID to template

# Route for user profile (GET for viewing, POST for updating)
@app.route('/profile/<int:user_id>', methods=['GET', 'POST'])
def profile(user_id):
    # Verify user is logged in and accessing their own profile
    if 'user_id' not in session or session['user_id'] != user_id:
        flash("Unauthorized access", "error")
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Get basic user info
    cursor.execute("SELECT username, city_code, postal_code FROM User WHERE userID = %s", (user_id,))
    user_row = cursor.fetchone()
    username = user_row['username'] if user_row else 'User'
    user_city_code = user_row['city_code']
    user_postal_code = user_row['postal_code']

    # Get all cities for dropdown
    cursor.execute("SELECT city_code, city_name FROM City ORDER BY city_name ASC")
    cities = cursor.fetchall()

    # Get all neighborhoods for dropdown
    cursor.execute("SELECT postal_code, area_name, city_code FROM Neighborhood ORDER BY area_name ASC")
    neighborhoods = cursor.fetchall()

    # Get all possible interests
    cursor.execute("SELECT interest_ID, interest_name FROM Interest ORDER BY interest_name ASC")
    all_interests = cursor.fetchall()

    if request.method == 'POST':
        # Handle profile update form submission
        city_code = request.form['city']
        postal_code = request.form['neighborhood']
        selected_interests = request.form.getlist('interests')

        # Update user's city and neighborhood
        cursor.execute("UPDATE User SET city_code = %s, postal_code = %s WHERE userID = %s",
                       (city_code, postal_code, user_id))

        # Update user's interests (delete old ones first)
        cursor.execute("DELETE FROM User_Interest WHERE userID = %s", (user_id,))
        for interest_id in selected_interests:
            cursor.execute("INSERT INTO User_Interest (userID, interest_ID) VALUES (%s, %s)",
                           (user_id, interest_id))

        conn.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('profile', user_id=user_id))

    # Get user's current interests
    cursor.execute("SELECT interest_ID FROM User_Interest WHERE userID = %s", (user_id,))
    user_interest_ids = [row['interest_ID'] for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return render_template('profile.html',
                           username=username,
                           cities=cities,
                           neighborhoods_json=neighborhoods,
                           all_interests=[(i['interest_ID'], i['interest_name']) for i in all_interests],
                           user_interest_ids=user_interest_ids,
                           user_city_code=user_city_code,
                           user_postal_code=user_postal_code)

# Route to view another user's profile
@app.route('/user/<int:profile_user_id>/view')
def view_profile(profile_user_id):
    if 'user_id' not in session:
        flash("Please log in", "error")
        return redirect(url_for('login'))

    viewer_id = session['user_id']
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Get basic profile info
    cursor.execute("""
        SELECT username, email FROM User WHERE userID = %s
    """, (profile_user_id,))
    profile = cursor.fetchone()

    if not profile:
        return redirect(url_for('dashboard'))

    # Get profile user's interests
    cursor.execute("""
        SELECT i.interest_name FROM User_Interest ui
        JOIN Interest i ON ui.interest_ID = i.interest_ID
        WHERE ui.userID = %s
    """, (profile_user_id,))
    interests = [row['interest_name'] for row in cursor.fetchall()]

    # Calculate average rating
    cursor.execute("""
        SELECT AVG(rating) AS avg_rating FROM User_Rating WHERE ratee_ID = %s
    """, (profile_user_id,))
    avg_row = cursor.fetchone()
    avg_rating = round(avg_row['avg_rating'], 2) if avg_row['avg_rating'] else "No ratings yet"

    # Get more detailed profile info including city and neighborhood
    cursor.execute("""
        SELECT u.username, u.email, c.city_name, n.area_name
        FROM User u
        LEFT JOIN City c ON u.city_code = c.city_code
        LEFT JOIN Neighborhood n ON u.postal_code = n.postal_code
        WHERE u.userID = %s
    """, (profile_user_id,))
    profile = cursor.fetchone()

    # Get all reviews for this user
    cursor.execute("""
        SELECT ur.rater_ID, ur.rating, ur.comments, u.username
        FROM User_Rating ur
        JOIN User u ON ur.rater_ID = u.userID
        WHERE ur.ratee_ID = %s
    """, (profile_user_id,))
    reviews = cursor.fetchall()

    # Check if viewer has already rated this user
    cursor.execute("""
        SELECT * FROM User_Rating WHERE rater_ID = %s AND ratee_ID = %s
    """, (viewer_id, profile_user_id))
    your_rating = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("view_profile.html",
                           profile=profile,
                           profile_user_id=profile_user_id,
                           interests=interests,
                           avg_rating=avg_rating,
                           reviews=reviews,
                           your_rating=your_rating,
                           viewer_id=viewer_id)

# Route to view own profile (simplified version)
@app.route('/profile/view')
def view_own_profile():
    if 'user_id' not in session:
        flash("Please log in", "error")
        return redirect(url_for('login'))

    viewer_id = session['user_id']
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Get user info with city and neighborhood
    cursor.execute("""
        SELECT u.username, u.email, c.city_name, n.area_name
        FROM User u
        LEFT JOIN City c ON u.city_code = c.city_code
        LEFT JOIN Neighborhood n ON u.postal_code = n.postal_code
        WHERE u.userID = %s
    """, (viewer_id,))
    profile = cursor.fetchone()

    # Get user's interests
    cursor.execute("""
        SELECT i.interest_name
        FROM User_Interest ui
        JOIN Interest i ON ui.interest_ID = i.interest_ID
        WHERE ui.userID = %s
    """, (viewer_id,))
    interests = [row['interest_name'] for row in cursor.fetchall()]

    # Calculate average rating
    cursor.execute("""
        SELECT AVG(rating) AS avg_rating
        FROM User_Rating
        WHERE ratee_ID = %s
    """, (viewer_id,))
    rating_row = cursor.fetchone()
    if rating_row and rating_row['avg_rating'] is not None:
        avg_rating = round(rating_row['avg_rating'], 2)
    else:
        avg_rating = "No ratings yet"

    # Get individual reviews
    cursor.execute("""
        SELECT ur.rater_ID, ur.rating, ur.comments, u.username
        FROM User_Rating ur
        JOIN User u ON ur.rater_ID = u.userID
        WHERE ur.ratee_ID = %s
    """, (viewer_id,))
    reviews = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("view_own_profile.html",
                           profile=profile,
                           interests=interests,
                           avg_rating=avg_rating,
                           reviews=reviews,
                           viewer_id=viewer_id)

# Route to list groups matching user's interests
@app.route('/groups')
def list_groups():
    if 'user_id' not in session:
        flash("Please log in", "error")
        return redirect(url_for('login'))

    user_id = session['user_id']
    page = request.args.get('page', 1, type=int)
    per_page = 10

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Get user's interest IDs
    cursor.execute("SELECT interest_ID FROM User_Interest WHERE userID = %s", (user_id,))
    user_interests = [row['interest_ID'] for row in cursor.fetchall()]

    if not user_interests:
        return render_template('groups.html', groups=[], memberships=set(), page=page, total_pages=0)

    # Prepare format string for SQL IN clause
    format_ids = ','.join(['%s'] * len(user_interests))

    # Count total matching groups
    count_query = f"""
        SELECT COUNT(DISTINCT g.group_ID) as total
        FROM GroupTable g
        JOIN Group_Interest gi ON g.group_ID = gi.group_ID
        WHERE gi.interest_ID IN ({format_ids})
    """
    cursor.execute(count_query, tuple(user_interests))
    total_groups = cursor.fetchone()['total']
    total_pages = (total_groups + per_page - 1) // per_page

    # Fetch paginated groups
    offset = (page - 1) * per_page
    query = f"""
        SELECT DISTINCT g.*
        FROM GroupTable g
        JOIN Group_Interest gi ON g.group_ID = gi.group_ID
        WHERE gi.interest_ID IN ({format_ids})
        ORDER BY g.group_name
        LIMIT %s OFFSET %s
    """
    cursor.execute(query, tuple(user_interests) + (per_page, offset))
    groups = cursor.fetchall()

    # Get IDs of groups user has joined
    cursor.execute("SELECT group_ID FROM User_Group WHERE userID = %s", (user_id,))
    joined_group_ids = {row['group_ID'] for row in cursor.fetchall()}

    cursor.close()
    conn.close()

    return render_template('groups.html', groups=groups, memberships=joined_group_ids, page=page, total_pages=total_pages)

# Route to create a new group
@app.route('/groups/create', methods=['GET', 'POST'])
def create_group():
    if 'user_id' not in session:
        flash("Please log in to create a group.", "error")
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Get all possible interests for group creation form
    cursor.execute("SELECT * FROM Interest ORDER BY interest_name")
    all_interests = cursor.fetchall()

    if request.method == 'POST':
        # Get form data
        group_name = request.form['group_name']
        description = request.form['description']
        selected_interests = request.form.getlist('interests')

        # Insert new group
        cursor.execute("INSERT INTO GroupTable (group_name, description) VALUES (%s, %s)", (group_name, description))
        conn.commit()
        group_id = cursor.lastrowid

        # Add selected interests to group
        for interest_id in selected_interests:
            cursor.execute("INSERT INTO Group_Interest (group_ID, interest_ID) VALUES (%s, %s)", (group_id, interest_id))

        # Add creator to group members
        cursor.execute("INSERT INTO User_Group (userID, group_ID) VALUES (%s, %s)", (session['user_id'], group_id))
        conn.commit()

        cursor.close()
        conn.close()
        return redirect(url_for('list_groups'))

    cursor.close()
    conn.close()
    return render_template("create_group.html", interests=all_interests)

# Route to join a group
@app.route('/groups/join/<int:group_id>', methods=['POST'])
def join_group(group_id):
    if 'user_id' not in session:
        flash("Login first", "error")
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor()

    # Add user to group (IGNORE prevents duplicate errors)
    cursor.execute("""
        INSERT IGNORE INTO User_Group (userID, group_ID)
        VALUES (%s, %s)
    """, (session['user_id'], group_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('list_groups'))

# Route to leave a group
@app.route('/groups/leave/<int:group_id>', methods=['POST'])
def leave_group(group_id):
    if 'user_id' not in session:
        flash("Please log in", "error")
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = connect_db()
    cursor = conn.cursor()

    # Remove user from group
    cursor.execute("DELETE FROM User_Group WHERE userID = %s AND group_ID = %s", (user_id, group_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('list_groups'))

# Route for group details page
@app.route('/groups/<int:group_id>')
def group_detail(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Verify user is a member of this group
    cursor.execute("SELECT * FROM User_Group WHERE userID = %s AND group_ID = %s", (user_id, group_id))
    if not cursor.fetchone():
        return redirect(url_for('list_groups'))

    # Get group info
    cursor.execute("SELECT * FROM GroupTable WHERE group_ID = %s", (group_id,))
    group = cursor.fetchone()

    # Get all posts in this group
    cursor.execute("""
        SELECT gp.post_ID, gp.content, gp.post_time, u.username, gp.userID
        FROM GroupPost gp
        JOIN User u ON gp.userID = u.userID
        WHERE gp.group_ID = %s
        ORDER BY gp.post_time DESC
    """, (group_id,))
    posts = cursor.fetchall()

    # Get comments for each post
    for post in posts:
        cursor.execute("""
            SELECT gc.comment_ID, gc.content, gc.comment_time, u.username, gc.userID
            FROM GroupComment gc
            JOIN User u ON gc.userID = u.userID
            WHERE gc.post_ID = %s
            ORDER BY gc.comment_time ASC
        """, (post['post_ID'],))
        post['comments'] = cursor.fetchall()

    # Get all events for this group
    cursor.execute("""
        SELECT e.*, 
               u.username AS creator_name,
               c.city_name,
               n.area_name,
               (SELECT COUNT(*) FROM event_participation ep WHERE ep.event_ID = e.event_ID) AS participant_count,
               EXISTS(
                   SELECT 1 FROM event_participation ep
                   WHERE ep.event_ID = e.event_ID AND ep.userID = %s
               ) AS is_participating
        FROM Event e
        JOIN User u ON e.creator_ID = u.userID
        LEFT JOIN City c ON e.city_code = c.city_code
        LEFT JOIN Neighborhood n ON e.postal_code = n.postal_code
        WHERE e.group_ID = %s
        ORDER BY e.event_date ASC, e.event_time ASC
    """, (user_id, group_id))
    events = cursor.fetchall()

    # Get all cities for event creation form
    cursor.execute("SELECT city_code, city_name FROM City ORDER BY city_name")
    cities = cursor.fetchall()

    # Get all neighborhoods for event creation form
    cursor.execute("SELECT postal_code, area_name, city_code FROM Neighborhood ORDER BY area_name")
    neighborhoods = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("group_detail.html",
                           group=group,
                           posts=posts,
                           events=events,
                           user_id=user_id,
                           cities=cities,
                           neighborhoods_json=neighborhoods)

# Route to create a post in a group
@app.route('/groups/<int:group_id>/post', methods=['POST'])
def create_post(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    content = request.form['content']
    conn = connect_db()
    cursor = conn.cursor()

    # Insert new group post
    cursor.execute("""
        INSERT INTO GroupPost (group_ID, userID, content)
        VALUES (%s, %s, %s)
    """, (group_id, session['user_id'], content))

    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('group_detail', group_id=group_id))

# Route to add comment to a group post
@app.route('/groups/<int:group_id>/comment/<int:post_id>', methods=['POST'])
def add_comment(group_id, post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    content = request.form['content']
    conn = connect_db()
    cursor = conn.cursor()
    
    # Insert new comment
    cursor.execute("""
        INSERT INTO GroupComment (post_id, userID, content)
        VALUES (%s, %s, %s)
    """, (post_id, session['user_id'], content))

    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('group_detail', group_id=group_id))

# Route to delete a group post
@app.route('/groups/<int:group_id>/post/delete/<int:post_id>', methods=['POST'])
def delete_post(group_id, post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor()

    # Delete post (only if user is author)
    cursor.execute("DELETE FROM GroupPost WHERE post_ID = %s AND userID = %s", (post_id, session['user_id']))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('group_detail', group_id=group_id))

# Route to delete a group comment
@app.route('/groups/<int:group_id>/comment/delete/<int:comment_id>', methods=['POST'])
def delete_comment(group_id, comment_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor()

    # Delete comment (only if user is author)
    cursor.execute("DELETE FROM GroupComment WHERE comment_ID = %s AND userID = %s", (comment_id, session['user_id']))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('group_detail', group_id=group_id))

# Route to create a group event
@app.route('/groups/<int:group_id>/events/create', methods=['POST'])
def create_event(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Get event details from form
    event_name = request.form['event_name']
    event_date = request.form['event_date']
    event_time = request.form['event_time']
    event_description = request.form['event_description']
    city_code = request.form.get('city')
    postal_code = request.form.get('neighborhood')

    conn = connect_db()
    cursor = conn.cursor()

    # Insert new event
    cursor.execute("""
        INSERT INTO Event (
            event_name, event_date, event_time, event_description,
            group_ID, creator_ID, city_code, postal_code
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (event_name, event_date, event_time, event_description,
          group_id, session['user_id'], city_code, postal_code))

    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('group_detail', group_id=group_id))

# Route to join an event
@app.route('/groups/<int:group_id>/event/<int:event_id>/join', methods=['POST'])
def join_event(group_id, event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor()

    # Add user to event participation
    cursor.execute("""
        INSERT IGNORE INTO event_participation (userID, event_ID) VALUES (%s, %s)
    """, (session['user_id'], event_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('group_detail', group_id=group_id))

# Route to leave an event
@app.route('/groups/<int:group_id>/event/<int:event_id>/leave', methods=['POST'])
def leave_event(group_id, event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor()
    
    # Remove user from event participation
    cursor.execute("""
        DELETE FROM event_participation WHERE userID = %s AND event_ID = %s
    """, (session['user_id'], event_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('group_detail', group_id=group_id))

# Route to delete an event
@app.route('/groups/<int:group_id>/event/<int:event_id>/delete', methods=['POST'])
def delete_event(group_id, event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor()

    # Verify current user is event creator
    cursor.execute("SELECT creator_ID FROM Event WHERE event_ID = %s", (event_id,))
    result = cursor.fetchone()
    if not result or result[0] != session['user_id']:
        flash("You are not allowed to delete this event.", "error")
        return redirect(url_for('group_detail', group_id=group_id))

    # Delete event
    cursor.execute("DELETE FROM Event WHERE event_ID = %s", (event_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('group_detail', group_id=group_id))

# Route to rate another user
@app.route('/rate/<int:profile_user_id>', methods=['POST'])
def rate_user(profile_user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    rater_id = session['user_id']
    rating = int(request.form['rating'])
    comment = request.form.get('comment')

    conn = connect_db()
    cursor = conn.cursor()

    # Check if users are or were friends (required for rating)
    cursor.execute("""
        SELECT 1 FROM Friendship 
        WHERE (user1_ID = %s AND user2_ID = %s) OR (user1_ID = %s AND user2_ID = %s)
        UNION
        SELECT 1 FROM FriendRequest 
        WHERE ((sender_id = %s AND receiver_id = %s) OR (sender_id = %s AND receiver_id = %s))
          AND status = 'accepted'
    """, (rater_id, profile_user_id, profile_user_id, rater_id,
          rater_id, profile_user_id, profile_user_id, rater_id))

    relationship = cursor.fetchone()

    if not relationship:
        cursor.close()
        conn.close()
        return redirect(url_for('view_profile', profile_user_id=profile_user_id, error="not_friends"))

    # Insert or update rating
    cursor.execute("""
        INSERT INTO User_Rating (rater_ID, ratee_ID, rating, comments)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE rating = %s, comments = %s
    """, (rater_id, profile_user_id, rating, comment, rating, comment))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('view_profile', profile_user_id=profile_user_id, success="rating_submitted"))

# Route to delete a rating
@app.route('/rate/<int:profile_user_id>/delete', methods=['POST'])
def delete_rating(profile_user_id):
    if 'user_id' not in session:
        flash("Please log in", "error")
        return redirect(url_for('login'))

    rater_id = session['user_id']

    conn = connect_db()
    cursor = conn.cursor()

    # Delete rating
    cursor.execute("""
        DELETE FROM User_Rating
        WHERE rater_ID = %s AND ratee_ID = %s
    """, (rater_id, profile_user_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('view_profile', profile_user_id=profile_user_id))

# Helper function to check if user is admin
def is_admin():
    if 'user_id' not in session:
        return False
    
    conn = connect_db()
    cursor = conn.cursor()

    # Query the database to get the 'is_admin' status of the current user
    cursor.execute("SELECT is_admin FROM User WHERE userID = %s", (session['user_id'],))
    result = cursor.fetchone()

    cursor.close()
    conn.close()

    # Return True if result exists and is_admin column == 1 (means user is admin), otherwise False
    return result and result[0] == 1

# Admin dashboard route
@app.route('/admin')
def admin_dashboard():
    if not is_admin():
        return redirect(url_for('dashboard'))
    
    return render_template('admin/dashboard.html')

# Admin users management route
@app.route('/admin/users')
def admin_users():
    if not is_admin():
        return redirect(url_for('dashboard'))

    # Pagination Setup
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Count total number of users for pagination
    cursor.execute("SELECT COUNT(*) AS total FROM User")
    total_users = cursor.fetchone()['total']
    total_pages = (total_users + per_page - 1) // per_page

    # Fetch paginated users with admin and restriction status
    cursor.execute("""
        SELECT userID, username, email, is_admin, is_restricted 
        FROM User ORDER BY userID ASC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    users = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin/users.html', users=users, page=page, total_pages=total_pages)

# Route to promote a user to admin (admin only)
@app.route('/admin/users/make_admin/<int:user_id>', methods=['POST'])
def make_user_admin(user_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    # Prevent an admin from promoting themselves again
    if session['user_id'] == user_id:
        return redirect(url_for('admin_users'))

    conn = connect_db()
    cursor = conn.cursor()

    # Promote the user to admin
    cursor.execute("UPDATE User SET is_admin = TRUE WHERE userID = %s", (user_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_users'))

# Route to revoke admin rights from a user (admin only)
@app.route('/admin/users/revoke_admin/<int:user_id>', methods=['POST'])
def revoke_user_admin(user_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    # Prevent an admin from revoking their own rights
    if session['user_id'] == user_id:
        return redirect(url_for('admin_users'))

    conn = connect_db()
    cursor = conn.cursor()

    # Revoke the user's admin rights
    cursor.execute("UPDATE User SET is_admin = FALSE WHERE userID = %s", (user_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_users'))

# Route to restrict a user from logging in (admin only)
@app.route('/admin/users/restrict/<int:user_id>', methods=['POST'])
def restrict_user(user_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    # Prevent admin from restricting themselves
    if session['user_id'] == user_id:
        return redirect(url_for('admin_users'))

    conn = connect_db()
    cursor = conn.cursor()

    # Set user as restricted
    cursor.execute("UPDATE User SET is_restricted = TRUE WHERE userID = %s", (user_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_users'))

# Route to remove restriction from a user (admin only)
@app.route('/admin/users/unrestrict/<int:user_id>', methods=['POST'])
def unrestrict_user(user_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    conn = connect_db()
    cursor = conn.cursor()

    # Remove restriction from user
    cursor.execute("UPDATE User SET is_restricted = FALSE WHERE userID = %s", (user_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_users'))

# Route to delete user (admin only)
@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
def admin_delete_user(user_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    # Prevent admins from deleting their own account
    if session['user_id'] == user_id:
        return redirect(url_for('admin_users'))

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Check if the user to delete exists and retrieve their admin status
    cursor.execute("SELECT is_admin FROM User WHERE userID = %s", (user_id,))
    user = cursor.fetchone()

    # If user doesn't exist, notify and redirect
    if not user:
        cursor.close()
        conn.close()
        return redirect(url_for('admin_users'))

    # Prevent deletion of other admins
    if user['is_admin']:
        cursor.close()
        conn.close()
        return redirect(url_for('admin_users'))

    try:
        # Delete related data manually in multiple tables to avoid foreign key constraint errors
        cursor.execute("DELETE FROM User_Rating WHERE rater_ID = %s OR ratee_ID = %s", (user_id, user_id))
        cursor.execute("DELETE FROM FriendRequest WHERE sender_id = %s OR receiver_id = %s", (user_id, user_id))
        cursor.execute("DELETE FROM Friendship WHERE user1_ID = %s OR user2_ID = %s", (user_id, user_id))
        cursor.execute("DELETE FROM Message WHERE sender_ID = %s OR receiver_ID = %s", (user_id, user_id))
        cursor.execute("DELETE FROM User_Interest WHERE userID = %s", (user_id,))
        cursor.execute("DELETE FROM User_Group WHERE userID = %s", (user_id,))
        cursor.execute("DELETE FROM event_participation WHERE userID = %s", (user_id,))
        cursor.execute("DELETE FROM GroupComment WHERE userID = %s", (user_id,))
        cursor.execute("DELETE FROM GroupPost WHERE userID = %s", (user_id,))

        # Delete any events created by this user
        cursor.execute("DELETE FROM Event WHERE creator_ID = %s", (user_id,))

        # Finally, delete the user record itself
        cursor.execute("DELETE FROM User WHERE userID = %s", (user_id,))

        conn.commit()

    except Exception as e:
        # Roll back the transaction on error and notify the user
        conn.rollback()

    cursor.close()
    conn.close()

    return redirect(url_for('admin_users'))

# Route for the admin to control interests
@app.route('/admin/interests')
def admin_interests():
    if not is_admin():
        return redirect(url_for('dashboard'))

    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Get total number of interests (for pagination)
    cursor.execute("SELECT COUNT(*) AS total FROM Interest")
    total_interests = cursor.fetchone()['total']
    total_pages = (total_interests + per_page - 1) // per_page

    # Fetch only interests for current page
    cursor.execute("SELECT * FROM Interest ORDER BY interest_ID LIMIT %s OFFSET %s", (per_page, offset))
    interests = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin/interests.html', interests=interests, page=page, total_pages=total_pages)

# Route for admin to add a new interest
@app.route('/admin/interests/add', methods=['POST'])
def add_interest():
    if not is_admin():
        return redirect(url_for('dashboard'))
    
    interest_name = request.form['interest_name']
    category = request.form['category']
    page = request.form.get('page', 1, type=int)  # Current page to return to after adding

    conn = connect_db()
    cursor = conn.cursor()

    # Insert the new interest into the Interest table
    cursor.execute(
        "INSERT INTO Interest (interest_name, category) VALUES (%s, %s)", 
        (interest_name, category)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_interests', page=page))

# Route for admin to edit an existing interest
@app.route('/admin/interests/edit/<int:interest_id>', methods=['POST'])
def edit_interest(interest_id):
    if not is_admin():
        return redirect(url_for('dashboard'))
    
    interest_name = request.form['interest_name']
    category = request.form['category']
    page = request.form.get('page', 1, type=int)  # Current page to return to after editing

    conn = connect_db()
    cursor = conn.cursor()

    # Update the interest in the database
    cursor.execute(
        "UPDATE Interest SET interest_name=%s, category=%s WHERE interest_ID=%s",
        (interest_name, category, interest_id)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_interests', page=page))

# Route for admin to delete an interest
@app.route('/admin/interests/delete/<int:interest_id>', methods=['POST'])
def delete_interest(interest_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    page = request.form.get('page', 1, type=int)

    conn = connect_db()
    cursor = conn.cursor()

    # Delete the interest from the database 
    cursor.execute("DELETE FROM Interest WHERE interest_ID=%s", (interest_id,))
    
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_interests', page=page))

# Admin groups management route
@app.route('/admin/groups')
def admin_groups():
    if not is_admin():
        return redirect(url_for('dashboard'))

    # Pagination setup
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Count total groups
    cursor.execute("SELECT COUNT(*) AS total FROM GroupTable")
    total_groups = cursor.fetchone()['total']
    total_pages = (total_groups + per_page - 1) // per_page

    # Fetch paginated groups
    cursor.execute("""
        SELECT group_ID, group_name, description
        FROM GroupTable
        ORDER BY group_ID ASC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    groups = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin/groups.html', groups=groups, page=page, total_pages=total_pages)

# Route to delete group (admin only)
@app.route('/admin/groups/delete/<int:group_id>', methods=['POST'])
def admin_delete_group(group_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    conn = connect_db()
    cursor = conn.cursor()

    # Delete the group with the given group_id
    cursor.execute("DELETE FROM GroupTable WHERE group_ID = %s", (group_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_groups'))

# Admin posts management route
@app.route('/admin/posts')
def admin_posts():
    if not is_admin():
        return redirect(url_for('dashboard'))

    # Pagination setup
    page = request.args.get('page', default=1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Count total posts
    cursor.execute("SELECT COUNT(*) AS total FROM GroupPost")
    total_posts = cursor.fetchone()['total']
    total_pages = (total_posts + per_page - 1) // per_page

    # Fetch paginated posts with group info
    cursor.execute("""
        SELECT gp.post_ID, gp.content, gp.post_time, g.group_name, u.username
        FROM GroupPost gp
        JOIN GroupTable g ON gp.group_ID = g.group_ID
        JOIN User u ON gp.userID = u.userID
        ORDER BY gp.post_time DESC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    posts = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin/posts.html', posts=posts, page=page, total_pages=total_pages)

# Route to delete post (admin only)
@app.route('/admin/posts/delete/<int:post_id>', methods=['POST'])
def admin_delete_post(post_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    conn = connect_db()
    cursor = conn.cursor()

    # Delete the post with the given post_id
    cursor.execute("DELETE FROM GroupPost WHERE post_ID = %s", (post_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_posts'))

# Admin events management route
@app.route('/admin/events')
def admin_events():
    if not is_admin():
        return redirect(url_for('dashboard'))

    # Pagination setup
    page = request.args.get('page', default=1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Count total events
    cursor.execute("SELECT COUNT(*) AS count FROM Event")
    total_events = cursor.fetchone()['count']
    total_pages = (total_events + per_page - 1) // per_page

    # Fetch paginated events with group info
    cursor.execute("""
        SELECT e.event_ID, e.event_name, e.event_date, g.group_name
        FROM Event e
        JOIN GroupTable g ON e.group_ID = g.group_ID
        ORDER BY e.event_date ASC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    events = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin/events.html', events=events, page=page, total_pages=total_pages)

# Route to delete event (admin only)
@app.route('/admin/events/delete/<int:event_id>', methods=['POST'])
def admin_delete_event(event_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    conn = connect_db()
    cursor = conn.cursor()

    # Delete the event with the specified event_id
    cursor.execute("DELETE FROM Event WHERE event_ID = %s", (event_id,))
    
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_events'))

# Admin ratings management route
@app.route('/admin/ratings')
def admin_ratings():
    if not is_admin():
        return redirect(url_for('dashboard'))

    # Pagination setup
    page = request.args.get('page', default=1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Count total ratings
    cursor.execute("SELECT COUNT(*) AS total FROM User_Rating")
    total_ratings = cursor.fetchone()['total']
    total_pages = (total_ratings + per_page - 1) // per_page

    # Fetch paginated ratings with usernames
    cursor.execute("""
        SELECT ur.rater_ID, ur.ratee_ID, ur.rating, ur.comments, u.username
        FROM User_Rating ur
        JOIN User u ON ur.ratee_ID = u.userID
        ORDER BY ur.ratee_ID
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    ratings = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('admin/ratings.html', ratings=ratings, page=page, total_pages=total_pages)

# Route to delete rating (admin only)
@app.route('/admin/ratings/delete/<int:rater_id>/<int:ratee_id>', methods=['POST'])
def admin_delete_rating(rater_id, ratee_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    conn = connect_db()
    cursor = conn.cursor()

    # Delete the rating given by rater_id to ratee_id
    cursor.execute("DELETE FROM User_Rating WHERE rater_ID = %s AND ratee_ID = %s", (rater_id, ratee_id))

    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('admin_ratings'))

# Main entry point
if __name__ == '__main__':
    app.run(debug=True)  # Run Flask app in debug mode