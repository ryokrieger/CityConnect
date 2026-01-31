# ============================================================================
# IMPORTS AND CONFIGURATION
# ============================================================================

from flask import Flask, render_template, request, redirect, url_for, flash, session
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

# Load .env file
load_dotenv()

# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Database configuration
database_url = os.getenv("DATABASE_URL")

if database_url:
    # Parse DATABASE_URL for Render deployment
    url = urlparse(database_url)
    db_config = {
        'host': url.hostname,
        'user': url.username,
        'password': url.password,
        'dbname': url.path[1:],  # Remove leading '/'
        'port': url.port or 5432
    }
else:
    # Use individual environment variables (local development)
    db_config = {
        'host': os.getenv("DB_HOST"),
        'user': os.getenv("DB_USER"),
        'password': os.getenv("DB_PASSWORD"),
        'dbname': os.getenv("DB_NAME")
    }

# ============================================================================
# DATABASE HELPER FUNCTION
# ============================================================================

# Helper function to connect to PostgreSQL database
def connect_db():
    return psycopg2.connect(**db_config)

# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

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
        cursor.execute("SELECT userid, password, is_restricted FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        # Validate user credentials and check restriction status
        if user and user[1] == password:
            # Check if user is restricted from logging in
            if user[2] == True:  # is_restricted = TRUE
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
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Fetch all cities for dropdown
    cursor.execute("SELECT city_code, city_name FROM city ORDER BY city_name")
    cities = cursor.fetchall()

    # Fetch all neighborhoods for dropdown
    cursor.execute("SELECT postal_code, area_name, city_code FROM neighborhood ORDER BY area_name")
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
            # Insert new user into users table
            cursor.execute("""
                INSERT INTO users (username, email, gender, password, city_code, postal_code)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (username, email, gender, password, city_code, postal_code))
            conn.commit()
            flash('Signup successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except psycopg2.Error as err:
            conn.rollback()
            flash(f'Error: {err}', 'danger')
            
    cursor.close()
    conn.close()

    return render_template('signup.html',
                           cities=cities,
                           neighborhoods=neighborhoods,
                           neighborhoods_json=neighborhoods)

# ============================================================================
# DASHBOARD AND PROFILE ROUTES
# ============================================================================

# Dashboard route - main page after login
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Please log in", "error")
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get current user's basic info
    cursor.execute("SELECT username, city_code FROM users WHERE userid = %s", (session['user_id'],))
    user = cursor.fetchone()

    # Get city name
    cursor.execute("SELECT city_name FROM city WHERE city_code = %s", (user['city_code'],))
    city = cursor.fetchone()['city_name'] if user['city_code'] else 'Unknown'

    # Check if user is admin
    cursor.execute("SELECT is_admin FROM users WHERE userid = %s", (session['user_id'],))
    is_admin = cursor.fetchone()['is_admin'] == True

    cursor.close()
    conn.close()

    return render_template("dashboard.html",
                           username=user['username'],
                           city_name=city,
                           is_admin=is_admin)

# Route to view own profile
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash("Please log in", "error")
        return redirect(url_for('login'))

    viewer_id = session['user_id']

    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get user info
    cursor.execute("""
        SELECT u.username, u.email, c.city_name, n.area_name
        FROM users u
        LEFT JOIN city c ON u.city_code = c.city_code
        LEFT JOIN neighborhood n ON u.postal_code = n.postal_code
        WHERE u.userid = %s
    """, (viewer_id,))
    profile = cursor.fetchone()

    # Get user's interests
    cursor.execute("""
        SELECT i.interest_name
        FROM user_interest ui
        JOIN interest i ON ui.interest_id = i.interest_id
        WHERE ui.userid = %s
    """, (viewer_id,))
    interests = [row['interest_name'] for row in cursor.fetchall()]

    # Calculate average rating
    cursor.execute("""
        SELECT AVG(rating) AS avg_rating
        FROM user_rating
        WHERE ratee_id = %s
    """, (viewer_id,))
    rating_row = cursor.fetchone()
    if rating_row and rating_row['avg_rating'] is not None:
        avg_rating = round(rating_row['avg_rating'], 2)
    else:
        avg_rating = "No ratings yet"

    # Get individual reviews
    cursor.execute("""
        SELECT ur.rater_id, ur.rating, ur.comments, u.username
        FROM user_rating ur
        JOIN users u ON ur.rater_id = u.userid
        WHERE ur.ratee_id = %s
    """, (viewer_id,))
    reviews = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("profile.html",
                           profile=profile,
                           interests=interests,
                           avg_rating=avg_rating,
                           reviews=reviews,
                           viewer_id=viewer_id)

# Route for editing profile (GET for viewing, POST for updating)
@app.route('/profile/<int:user_id>', methods=['GET', 'POST'])
def edit_profile(user_id):
    # Verify user is logged in and accessing their own profile
    if 'user_id' not in session or session['user_id'] != user_id:
        flash("Unauthorized access", "error")
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get basic user info
    cursor.execute("SELECT username, city_code, postal_code FROM users WHERE userid = %s", (user_id,))
    user_row = cursor.fetchone()
    username = user_row['username'] if user_row else 'User'
    user_city_code = user_row['city_code']
    user_postal_code = user_row['postal_code']

    # Get all cities for dropdown
    cursor.execute("SELECT city_code, city_name FROM city ORDER BY city_name ASC")
    cities = cursor.fetchall()

    # Get all neighborhoods for dropdown
    cursor.execute("SELECT postal_code, area_name, city_code FROM neighborhood ORDER BY area_name ASC")
    neighborhoods = cursor.fetchall()

    # Get all possible interests
    cursor.execute("SELECT interest_id, interest_name FROM interest ORDER BY interest_name ASC")
    all_interests = cursor.fetchall()

    if request.method == 'POST':
        # Handle profile update form submission
        city_code = request.form['city']
        postal_code = request.form['neighborhood']
        selected_interests = request.form.getlist('interests')

        # Update user's city and neighborhood
        cursor.execute("UPDATE users SET city_code = %s, postal_code = %s WHERE userid = %s",
                       (city_code, postal_code, user_id))

        # Update user's interests (delete old ones first)
        cursor.execute("DELETE FROM user_interest WHERE userid = %s", (user_id,))
        for interest_id in selected_interests:
            cursor.execute("INSERT INTO user_interest (userid, interest_id) VALUES (%s, %s)",
                           (user_id, interest_id))

        conn.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('profile', user_id=user_id))

    # Get user's current interests
    cursor.execute("SELECT interest_id FROM user_interest WHERE userid = %s", (user_id,))
    user_interest_ids = [row['interest_id'] for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return render_template('edit_profile.html',
                           username=username,
                           cities=cities,
                           neighborhoods_json=neighborhoods,
                           all_interests=[(i['interest_id'], i['interest_name']) for i in all_interests],
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
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get basic profile info
    cursor.execute("""
        SELECT username, email FROM users WHERE userid = %s
    """, (profile_user_id,))
    profile = cursor.fetchone()

    if not profile:
        return redirect(url_for('dashboard'))

    # Get profile user's interests
    cursor.execute("""
        SELECT i.interest_name FROM user_interest ui
        JOIN interest i ON ui.interest_id = i.interest_id
        WHERE ui.userid = %s
    """, (profile_user_id,))
    interests = [row['interest_name'] for row in cursor.fetchall()]

    # Calculate average rating
    cursor.execute("""
        SELECT AVG(rating) AS avg_rating FROM user_rating WHERE ratee_id = %s
    """, (profile_user_id,))
    avg_row = cursor.fetchone()
    avg_rating = round(avg_row['avg_rating'], 2) if avg_row['avg_rating'] else "No ratings yet"

    # Get more detailed profile info including city and neighborhood
    cursor.execute("""
        SELECT u.username, u.email, c.city_name, n.area_name
        FROM users u
        LEFT JOIN city c ON u.city_code = c.city_code
        LEFT JOIN neighborhood n ON u.postal_code = n.postal_code
        WHERE u.userid = %s
    """, (profile_user_id,))
    profile = cursor.fetchone()

    # Get all reviews for this user
    cursor.execute("""
        SELECT ur.rater_id, ur.rating, ur.comments, u.username
        FROM user_rating ur
        JOIN users u ON ur.rater_id = u.userid
        WHERE ur.ratee_id = %s
    """, (profile_user_id,))
    reviews = cursor.fetchall()

    # Check if viewer has already rated this user
    cursor.execute("""
        SELECT * FROM user_rating WHERE rater_id = %s AND ratee_id = %s
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
        SELECT 1 FROM friendship 
        WHERE (user1_id = %s AND user2_id = %s) OR (user1_id = %s AND user2_id = %s)
        UNION
        SELECT 1 FROM friendrequest 
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
        INSERT INTO user_rating (rater_id, ratee_id, rating, comments)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (rater_id, ratee_id)
        DO UPDATE SET rating = %s, comments = %s
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
        DELETE FROM user_rating
        WHERE rater_id = %s AND ratee_id = %s
    """, (rater_id, profile_user_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('view_profile', profile_user_id=profile_user_id))

# ============================================================================
# USER MATCHING ROUTES
# ============================================================================

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
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get current user's location (city & neighborhood)
    cursor.execute("SELECT city_code, postal_code FROM users WHERE userid = %s", (user_id,))
    row = cursor.fetchone()
    user_city_code = row['city_code']
    user_postal = row['postal_code']

    # Get current user's interest IDs
    cursor.execute("SELECT interest_id FROM user_interest WHERE userid = %s", (user_id,))
    interest_ids = [r['interest_id'] for r in cursor.fetchall()]

    if not interest_ids:
        cursor.close()
        conn.close()
        flash("You haven't selected any interests yet—add some to see matches.", "warning")
        return redirect(url_for('edit_profile', user_id=user_id))

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
            SELECT DISTINCT u.userid
            FROM users u
            JOIN user_interest ui ON u.userid = ui.userid
            WHERE u.userid != %s
              AND {scope_condition}
              AND ui.interest_id IN ({in_placeholders})
              AND u.userid NOT IN (
                  SELECT user2_id FROM friendship WHERE user1_id = %s
                  UNION
                  SELECT user1_id FROM friendship WHERE user2_id = %s
              )
        ) AS sub
    """
    cursor.execute(count_sql, (user_id, scope_value, *interest_ids, user_id, user_id))
    total_users = cursor.fetchone()['total']
    total_pages = (total_users + per_page - 1) // per_page

    # Fetch page of users with shared interest count (sorted by match count DESC)
    page_sql = f"""
        SELECT
            u.userid,
            u.username,
            u.email,
            COUNT(ui.interest_id) AS shared_count
        FROM users u
        JOIN user_interest ui ON u.userid = ui.userid
        WHERE u.userid != %s
          AND {scope_condition}
          AND ui.interest_id IN ({in_placeholders})
          AND u.userid NOT IN (
              SELECT user2_id FROM friendship WHERE user1_id = %s
              UNION
              SELECT user1_id FROM friendship WHERE user2_id = %s
          )
        GROUP BY u.userid, u.username, u.email
        ORDER BY shared_count DESC, u.username ASC
        LIMIT %s OFFSET %s
    """
    cursor.execute(page_sql, (user_id, scope_value, *interest_ids, user_id, user_id, per_page, offset))
    users_page = cursor.fetchall()

    # Collect IDs on this page to fetch the actual shared interest names
    matches = []
    if users_page:
        page_user_ids = [u['userid'] for u in users_page]
        user_id_placeholders = ','.join(['%s'] * len(page_user_ids))

        interests_sql = f"""
            SELECT ui.userid, i.interest_name
            FROM user_interest ui
            JOIN interest i ON ui.interest_id = i.interest_id
            WHERE ui.userid IN ({user_id_placeholders})
              AND ui.interest_id IN ({in_placeholders})
            ORDER BY i.interest_name
        """
        cursor.execute(interests_sql, (*page_user_ids, *interest_ids))
        interest_rows = cursor.fetchall()

        interest_map = {}
        for r in interest_rows:
            interest_map.setdefault(r['userid'], []).append(r['interest_name'])

        # Assemble final list
        for u in users_page:
            matches.append({
                'userid': u['userid'],
                'username': u['username'],
                'email': u['email'],
                'shared_interests': interest_map.get(u['userid'], []),
                'shared_count': u['shared_count']
            })

    # Friend request statuses involving the current user <-> page users
    if users_page:
        cursor.execute("""
            SELECT sender_id, receiver_id, status
            FROM friendrequest
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

    return render_template("similar_interests.html",
                           scope=scope,
                           matches=matches,
                           request_status=request_status,
                           page=page,
                           total_pages=total_pages)

# ============================================================================
# FRIEND REQUEST ROUTES
# ============================================================================

# Route to send friend request
@app.route('/friend_request/send/<int:receiver_id>', methods=['POST'])
def send_friend_request(receiver_id):
    if 'user_id' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('login'))

    sender_id = session['user_id']

    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Check if a pending friend request already exists from this user to the receiver
    cursor.execute("""
        SELECT 1 FROM friendrequest
        WHERE sender_id = %s AND receiver_id = %s AND status = 'pending'
    """, (sender_id, receiver_id))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return redirect(request.referrer or url_for('similar_interests_root'))

    # Check if the users are already friends
    cursor.execute("""
        SELECT 1 FROM friendship
        WHERE (user1_id = %s AND user2_id = %s) OR (user1_id = %s AND user2_id = %s)
    """, (sender_id, receiver_id, receiver_id, sender_id))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        flash("You are already friends.", "info")
        return redirect(request.referrer or url_for('similar_interests_root'))

    # Insert a new friend request into the friendrequest table
    cursor.execute("""
        INSERT INTO friendrequest (sender_id, receiver_id) VALUES (%s, %s)
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
        DELETE FROM friendrequest
        WHERE sender_id = %s AND receiver_id = %s AND status = 'pending'
    """, (user_id, receiver_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(request.referrer or url_for('similar_interests_root'))

# Route to manage friend requests
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
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Count total pending requests
    cursor.execute("""
        SELECT COUNT(*) as total
        FROM friendrequest fr
        WHERE fr.receiver_id = %s AND fr.status = 'pending'
    """, (session['user_id'],))
    total_requests = cursor.fetchone()['total']
    total_pages = (total_requests + per_page - 1) // per_page

    # Get paginated list of pending requests
    cursor.execute("""
        SELECT fr.request_id, u.userid, u.username, u.email
        FROM friendrequest fr
        JOIN users u ON fr.sender_id = u.userid
        WHERE fr.receiver_id = %s AND fr.status = 'pending'
        LIMIT %s OFFSET %s
    """, (session['user_id'], per_page, offset))

    requests = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('manage_requests.html',
                           requests=requests,
                           page=page,
                           total_pages=total_pages)

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
        SELECT sender_id, receiver_id FROM friendrequest 
        WHERE request_id = %s AND status = 'pending'
    """, (request_id,))
    result = cursor.fetchone()

    if result:
        sender_id, receiver_id = result
        # Update request status to 'accepted'
        cursor.execute("""
            UPDATE friendrequest SET status = 'accepted' WHERE request_id = %s
        """, (request_id,))
        # Create friendship record
        cursor.execute("""
            INSERT INTO friendship (user1_id, user2_id) VALUES (%s, %s)
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
        UPDATE friendrequest SET status = 'declined' 
        WHERE request_id = %s AND receiver_id = %s
    """, (request_id, session['user_id']))
    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for('manage_friend_requests'))

# ============================================================================
# FRIENDS MANAGEMENT ROUTES
# ============================================================================

# Route to view friends
@app.route('/friends')
def friends():
    if 'user_id' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('login'))

    user_id = session['user_id']

    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Count total friends
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM friendship f
        JOIN users u ON (
            (f.user1_id = u.userid AND f.user2_id = %s) OR 
            (f.user2_id = u.userid AND f.user1_id = %s)
        )
    """, (user_id, user_id))
    total_friends = cursor.fetchone()['total']
    total_pages = (total_friends + per_page - 1) // per_page

    # Fetch paginated friends list
    cursor.execute("""
        SELECT u.userid, u.username, u.email
        FROM friendship f
        JOIN users u ON (
            (f.user1_id = u.userid AND f.user2_id = %s) OR 
            (f.user2_id = u.userid AND f.user1_id = %s)
        )
        LIMIT %s OFFSET %s
    """, (user_id, user_id, per_page, offset))

    friends = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('friends.html',
                           friends=friends,
                           page=page,
                           total_pages=total_pages)

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
        DELETE FROM friendship 
        WHERE (user1_id = %s AND user2_id = %s)
           OR (user1_id = %s AND user2_id = %s)
    """, (user_id, friend_id, friend_id, user_id))

    # Also delete any accepted friend requests between these users
    cursor.execute("""
        DELETE FROM friendrequest
        WHERE ((sender_id = %s AND receiver_id = %s) OR
               (sender_id = %s AND receiver_id = %s))
          AND status = 'accepted'
    """, (user_id, friend_id, friend_id, user_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('friends'))

# ============================================================================
# CHAT ROUTES
# ============================================================================

# Route for chatting with a friend
@app.route('/chat/<int:friend_id>', methods=['GET', 'POST'])
def chat(friend_id):
    if 'user_id' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('login'))

    user_id = session['user_id']

    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Verify that friendship exists between current user and friend
    # Check both directions since friendship can be stored either way
    cursor.execute("""
        SELECT * FROM friendship 
        WHERE (user1_id = %s AND user2_id = %s)
           OR (user1_id = %s AND user2_id = %s)
    """, (user_id, friend_id, friend_id, user_id))
    friendship = cursor.fetchone()

    # If no friendship exists, redirect to friends list
    if not friendship:
        return redirect(url_for('friends'))

    # Handle POST request when user sends a new message
    if request.method == 'POST':
        # Get message content from form
        content = request.form['message']
        
        # Insert new message into database
        cursor.execute("""
            INSERT INTO message (sender_id, receiver_id, content)
            VALUES (%s, %s, %s)
        """, (user_id, friend_id, content))
        conn.commit()

    # Fetch all messages between current user and friend
    # Join with users table to get sender's username
    cursor.execute("""
        SELECT m.*, u.username AS sender_name
        FROM message m
        JOIN users u ON m.sender_id = u.userid
        WHERE (sender_id = %s AND receiver_id = %s)
           OR (sender_id = %s AND receiver_id = %s)
        ORDER BY timestamp ASC
    """, (user_id, friend_id, friend_id, user_id))
    messages = cursor.fetchall()

    # Get friend's username for display
    cursor.execute("SELECT username FROM users WHERE userid = %s", (friend_id,))
    friend_name = cursor.fetchone()['username']

    cursor.close()
    conn.close()

    return render_template("chat.html",
                           messages=messages,
                           friend_name=friend_name,
                           friend_id=friend_id,
                           current_user_id=user_id)

# ============================================================================
# GROUP MANAGEMENT ROUTES
# ============================================================================

# Route to groups matching user's interests
@app.route('/groups')
def groups():
    if 'user_id' not in session:
        flash("Please log in", "error")
        return redirect(url_for('login'))

    user_id = session['user_id']

    page = request.args.get('page', 1, type=int)
    per_page = 10

    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get user's interest IDs
    cursor.execute("SELECT interest_id FROM user_interest WHERE userid = %s", (user_id,))
    user_interests = [row['interest_id'] for row in cursor.fetchall()]

    if not user_interests:
        return render_template('groups.html',
                               groups=[],
                               memberships=set(),
                               page=page,
                               total_pages=0)

    # Prepare format string for SQL IN clause
    format_ids = ','.join(['%s'] * len(user_interests))

    # Count total matching groups
    count_query = f"""
        SELECT COUNT(DISTINCT g.group_id) as total
        FROM grouptable g
        JOIN group_interest gi ON g.group_id = gi.group_id
        WHERE gi.interest_id IN ({format_ids})
    """
    cursor.execute(count_query, tuple(user_interests))
    total_groups = cursor.fetchone()['total']
    total_pages = (total_groups + per_page - 1) // per_page

    # Fetch paginated groups
    offset = (page - 1) * per_page
    query = f"""
        SELECT DISTINCT g.*
        FROM grouptable g
        JOIN group_interest gi ON g.group_id = gi.group_id
        WHERE gi.interest_id IN ({format_ids})
        ORDER BY g.group_name
        LIMIT %s OFFSET %s
    """
    cursor.execute(query, tuple(user_interests) + (per_page, offset))
    groups = cursor.fetchall()

    # Get IDs of groups user has joined
    cursor.execute("SELECT group_id FROM user_group WHERE userid = %s", (user_id,))
    joined_group_ids = {row['group_id'] for row in cursor.fetchall()}

    cursor.close()
    conn.close()

    return render_template('groups.html',
                           groups=groups,
                           memberships=joined_group_ids, 
                           page=page,
                           total_pages=total_pages)

# Route to join a group
@app.route('/groups/join/<int:group_id>', methods=['POST'])
def join_group(group_id):
    if 'user_id' not in session:
        flash("Login first", "error")
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor()

    # Add user to group (ON CONFLICT DO NOTHING prevents duplicate errors)
    cursor.execute("""
        INSERT INTO user_group (userid, group_id)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
    """, (session['user_id'], group_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('groups'))

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
    cursor.execute("DELETE FROM user_group WHERE userid = %s AND group_id = %s", (user_id, group_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('groups'))

# Route to create a new group
@app.route('/groups/create', methods=['GET', 'POST'])
def create_group():
    if 'user_id' not in session:
        flash("Please log in to create a group.", "error")
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get all possible interests for group creation form
    cursor.execute("SELECT * FROM interest ORDER BY interest_name")
    all_interests = cursor.fetchall()

    if request.method == 'POST':
        # Get form data
        group_name = request.form['group_name']
        description = request.form['description']
        selected_interests = request.form.getlist('interests')

        # Insert new group
        cursor.execute("INSERT INTO grouptable (group_name, description) VALUES (%s, %s) RETURNING group_id", (group_name, description))
        group_id = cursor.fetchone()['group_id']

        # Add selected interests to group
        for interest_id in selected_interests:
            cursor.execute("INSERT INTO group_interest (group_id, interest_id) VALUES (%s, %s)", (group_id, interest_id))

        # Add creator to group members
        cursor.execute("INSERT INTO user_group (userid, group_id) VALUES (%s, %s)", (session['user_id'], group_id))

        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for('groups'))

    cursor.close()
    conn.close()

    return render_template("create_group.html",
                           interests=all_interests)

# Route for group details page
@app.route('/groups/<int:group_id>')
def group(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Verify user is a member of this group
    cursor.execute("SELECT * FROM user_group WHERE userid = %s AND group_id = %s", (user_id, group_id))
    if not cursor.fetchone():
        return redirect(url_for('groups'))

    # Get group info
    cursor.execute("SELECT * FROM grouptable WHERE group_id = %s", (group_id,))
    group = cursor.fetchone()

    # Get all posts in this group
    cursor.execute("""
        SELECT gp.post_id, gp.content, gp.post_time, u.username, gp.userid
        FROM grouppost gp
        JOIN users u ON gp.userid = u.userid
        WHERE gp.group_id = %s
        ORDER BY gp.post_time DESC
    """, (group_id,))
    posts = cursor.fetchall()

    # Get comments for each post
    for post in posts:
        cursor.execute("""
            SELECT gc.comment_id, gc.content, gc.comment_time, u.username, gc.userid
            FROM groupcomment gc
            JOIN users u ON gc.userid = u.userid
            WHERE gc.post_id = %s
            ORDER BY gc.comment_time ASC
        """, (post['post_id'],))
        post['comments'] = cursor.fetchall()

    # Get all events for this group
    cursor.execute("""
        SELECT e.*, 
               u.username AS creator_name,
               c.city_name,
               n.area_name,
               (SELECT COUNT(*) FROM event_participation ep WHERE ep.event_id = e.event_id) AS participant_count,
               EXISTS(
                   SELECT 1 FROM event_participation ep
                   WHERE ep.event_id = e.event_id AND ep.userid = %s
               ) AS is_participating
        FROM event e
        JOIN users u ON e.creator_id = u.userid
        LEFT JOIN city c ON e.city_code = c.city_code
        LEFT JOIN neighborhood n ON e.postal_code = n.postal_code
        WHERE e.group_id = %s
        ORDER BY e.event_date ASC, e.event_time ASC
    """, (user_id, group_id))
    events = cursor.fetchall()

    # Get all cities for event creation form
    cursor.execute("SELECT city_code, city_name FROM city ORDER BY city_name")
    cities = cursor.fetchall()

    # Get all neighborhoods for event creation form
    cursor.execute("SELECT postal_code, area_name, city_code FROM neighborhood ORDER BY area_name")
    neighborhoods = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("group.html",
                           group=group,
                           posts=posts,
                           events=events,
                           user_id=user_id,
                           cities=cities,
                           neighborhoods_json=neighborhoods)

# ============================================================================
# GROUP CONTENT ROUTES
# ============================================================================

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
        INSERT INTO grouppost (group_id, userid, content)
        VALUES (%s, %s, %s)
    """, (group_id, session['user_id'], content))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('group', group_id=group_id))

# Route to delete a group post
@app.route('/groups/<int:group_id>/post/delete/<int:post_id>', methods=['POST'])
def delete_post(group_id, post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor()

    # Delete post (only if user is author)
    cursor.execute("DELETE FROM grouppost WHERE post_id = %s AND userid = %s", (post_id, session['user_id']))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('group', group_id=group_id))

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
        INSERT INTO groupcomment (post_id, userid, content)
        VALUES (%s, %s, %s)
    """, (post_id, session['user_id'], content))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('group', group_id=group_id))

# Route to delete a comment on a group post
@app.route('/groups/<int:group_id>/comment/delete/<int:comment_id>', methods=['POST'])
def delete_comment(group_id, comment_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor()

    # Delete comment (only if user is author)
    cursor.execute("DELETE FROM groupcomment WHERE comment_id = %s AND userid = %s", (comment_id, session['user_id']))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('group', group_id=group_id))

# ============================================================================
# EVENT ROUTES
# ============================================================================

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
        INSERT INTO event (
            event_name, event_date, event_time, event_description,
            group_id, creator_id, city_code, postal_code
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (event_name, event_date, event_time, event_description,
          group_id, session['user_id'], city_code, postal_code))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('group', group_id=group_id))

# Route to delete a group event
@app.route('/groups/<int:group_id>/event/<int:event_id>/delete', methods=['POST'])
def delete_event(group_id, event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor()

    # Verify current user is event creator
    cursor.execute("SELECT creator_id FROM event WHERE event_id = %s", (event_id,))
    result = cursor.fetchone()
    if not result or result[0] != session['user_id']:
        flash("You are not allowed to delete this event.", "error")
        return redirect(url_for('group_detail', group_id=group_id))

    # Delete event
    cursor.execute("DELETE FROM event WHERE event_id = %s", (event_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('group', group_id=group_id))

# Route to join a group event
@app.route('/groups/<int:group_id>/event/<int:event_id>/join', methods=['POST'])
def join_event(group_id, event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor()

    # Add user to event participation
    cursor.execute("""
        INSERT INTO event_participation (userid, event_id) 
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
    """, (session['user_id'], event_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('group', group_id=group_id))

# Route to leave a group event
@app.route('/groups/<int:group_id>/event/<int:event_id>/leave', methods=['POST'])
def leave_event(group_id, event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor()
    
    # Remove user from event participation
    cursor.execute("""
        DELETE FROM event_participation WHERE userid = %s AND event_id = %s
    """, (session['user_id'], event_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('group', group_id=group_id))

# ============================================================================
# ADMIN HELPER FUNCTION
# ============================================================================

# Helper function to check if user is admin
def is_admin():
    if 'user_id' not in session:
        return False
    
    conn = connect_db()
    cursor = conn.cursor()

    # Search the database to get the 'is_admin' status of the current user
    cursor.execute("SELECT is_admin FROM users WHERE userid = %s", (session['user_id'],))
    result = cursor.fetchone()

    cursor.close()
    conn.close()

    # Return True if result exists and is_admin column == True (means user is admin), otherwise False
    return result and result[0] == True

# ============================================================================
# ADMIN DASHBOARD AND USER MANAGEMENT
# ============================================================================

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
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Count total number of users for pagination
    cursor.execute("SELECT COUNT(*) AS total FROM users")
    total_users = cursor.fetchone()['total']
    total_pages = (total_users + per_page - 1) // per_page

    # Fetch paginated users with admin and restriction status
    cursor.execute("""
        SELECT userid, username, email, is_admin, is_restricted 
        FROM users ORDER BY userid ASC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    users = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin/users.html',
                           users=users,
                           page=page,
                           total_pages=total_pages)

# Route to promote a user to admin (admin only)
@app.route('/admin/users/make_admin/<int:user_id>', methods=['POST'])
def make_user_admin(user_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    # Get current page from form data
    page = request.form.get('page', 1, type=int)
    
    # Prevent an admin from promoting themselves again
    if session['user_id'] == user_id:
        return redirect(url_for('admin_users', page=page))

    conn = connect_db()
    cursor = conn.cursor()

    # Promote the user to admin
    cursor.execute("UPDATE users SET is_admin = TRUE WHERE userid = %s", (user_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_users', page=page))

# Route to revoke admin rights from a user (admin only)
@app.route('/admin/users/revoke_admin/<int:user_id>', methods=['POST'])
def revoke_user_admin(user_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    # Get current page from form data
    page = request.form.get('page', 1, type=int)
    
    # Prevent an admin from revoking their own rights
    if session['user_id'] == user_id:
        return redirect(url_for('admin_users', page=page))

    conn = connect_db()
    cursor = conn.cursor()

    # Revoke the user's admin rights
    cursor.execute("UPDATE users SET is_admin = FALSE WHERE userid = %s", (user_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_users', page=page))

# Route to restrict a user from logging in (admin only)
@app.route('/admin/users/restrict/<int:user_id>', methods=['POST'])
def restrict_user(user_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    # Get current page from form data
    page = request.form.get('page', 1, type=int)
    
    # Prevent admin from restricting themselves
    if session['user_id'] == user_id:
        return redirect(url_for('admin_users', page=page))

    conn = connect_db()
    cursor = conn.cursor()

    # Set user as restricted
    cursor.execute("UPDATE users SET is_restricted = TRUE WHERE userid = %s", (user_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_users', page=page))

# Route to remove restriction from a user (admin only)
@app.route('/admin/users/unrestrict/<int:user_id>', methods=['POST'])
def unrestrict_user(user_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    # Get current page from form data
    page = request.form.get('page', 1, type=int)
    
    conn = connect_db()
    cursor = conn.cursor()

    # Remove restriction from user
    cursor.execute("UPDATE users SET is_restricted = FALSE WHERE userid = %s", (user_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_users', page=page))

# Route to delete user (admin only)
@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
def admin_delete_user(user_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    # Get current page from form data
    page = request.form.get('page', 1, type=int)
    
    # Prevent admins from deleting their own account
    if session['user_id'] == user_id:
        return redirect(url_for('admin_users', page=page))

    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Check if the user to delete exists and retrieve their admin status
    cursor.execute("SELECT is_admin FROM users WHERE userid = %s", (user_id,))
    user = cursor.fetchone()

    # If user doesn't exist, notify and redirect
    if not user:
        cursor.close()
        conn.close()
        return redirect(url_for('admin_users', page=page))

    # Prevent deletion of other admins
    if user['is_admin']:
        cursor.close()
        conn.close()
        return redirect(url_for('admin_users', page=page))

    try:
        # Delete related data manually in multiple tables to avoid foreign key constraint errors
        cursor.execute("DELETE FROM user_rating WHERE rater_id = %s OR ratee_id = %s", (user_id, user_id))
        cursor.execute("DELETE FROM friendrequest WHERE sender_id = %s OR receiver_id = %s", (user_id, user_id))
        cursor.execute("DELETE FROM friendship WHERE user1_id = %s OR user2_id = %s", (user_id, user_id))
        cursor.execute("DELETE FROM message WHERE sender_id = %s OR receiver_id = %s", (user_id, user_id))
        cursor.execute("DELETE FROM user_interest WHERE userid = %s", (user_id,))
        cursor.execute("DELETE FROM user_group WHERE userid = %s", (user_id,))
        cursor.execute("DELETE FROM event_participation WHERE userid = %s", (user_id,))
        cursor.execute("DELETE FROM groupcomment WHERE userid = %s", (user_id,))
        cursor.execute("DELETE FROM grouppost WHERE userid = %s", (user_id,))

        # Delete any events created by this user
        cursor.execute("DELETE FROM event WHERE creator_id = %s", (user_id,))

        # Finally, delete the user record itself
        cursor.execute("DELETE FROM users WHERE userid = %s", (user_id,))

        conn.commit()

    except Exception as e:
        # Roll back the transaction on error and notify the user
        conn.rollback()

    cursor.close()
    conn.close()

    return redirect(url_for('admin_users', page=page))

# ============================================================================
# ADMIN CONTENT MANAGEMENT
# ============================================================================

# Route for the admin to control interests
@app.route('/admin/interests')
def admin_interests():
    if not is_admin():
        return redirect(url_for('dashboard'))

    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get total number of interests (for pagination)
    cursor.execute("SELECT COUNT(*) AS total FROM interest")
    total_interests = cursor.fetchone()['total']
    total_pages = (total_interests + per_page - 1) // per_page

    # Fetch only interests for current page
    cursor.execute("SELECT * FROM interest ORDER BY interest_id LIMIT %s OFFSET %s", (per_page, offset))
    interests = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin/interests.html',
                           interests=interests,
                           page=page,
                           total_pages=total_pages)

# Route for admin to add a new interest
@app.route('/admin/interests/add', methods=['POST'])
def add_interest():
    if not is_admin():
        return redirect(url_for('dashboard'))
    
    interest_name = request.form['interest_name']
    category = request.form['category']
    page = request.form.get('page', 1, type=int)

    conn = connect_db()
    cursor = conn.cursor()

    # Insert the new interest into the interest table
    cursor.execute(
        "INSERT INTO interest (interest_name, category) VALUES (%s, %s)", 
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
    page = request.form.get('page', 1, type=int)

    conn = connect_db()
    cursor = conn.cursor()

    # Update the interest in the database
    cursor.execute(
        "UPDATE interest SET interest_name=%s, category=%s WHERE interest_id=%s",
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
    cursor.execute("DELETE FROM interest WHERE interest_id=%s", (interest_id,))
    
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
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Count total groups
    cursor.execute("SELECT COUNT(*) AS total FROM grouptable")
    total_groups = cursor.fetchone()['total']
    total_pages = (total_groups + per_page - 1) // per_page

    # Fetch paginated groups
    cursor.execute("""
        SELECT group_id, group_name, description
        FROM grouptable
        ORDER BY group_id ASC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    groups = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin/groups.html',
                           groups=groups,
                           page=page,
                           total_pages=total_pages)

# Route to delete group (admin only)
@app.route('/admin/groups/delete/<int:group_id>', methods=['POST'])
def admin_delete_group(group_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    # Get current page from form data
    page = request.form.get('page', 1, type=int)
    
    conn = connect_db()
    cursor = conn.cursor()

    # Delete the group with the given group_id
    cursor.execute("DELETE FROM grouptable WHERE group_id = %s", (group_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_groups', page=page))

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
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Count total posts
    cursor.execute("SELECT COUNT(*) AS total FROM grouppost")
    total_posts = cursor.fetchone()['total']
    total_pages = (total_posts + per_page - 1) // per_page

    # Fetch paginated posts with group info
    cursor.execute("""
        SELECT gp.post_id, gp.content, gp.post_time, g.group_name, u.username
        FROM grouppost gp
        JOIN grouptable g ON gp.group_id = g.group_id
        JOIN users u ON gp.userid = u.userid
        ORDER BY gp.post_time DESC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    posts = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin/posts.html',
                           posts=posts,
                           page=page,
                           total_pages=total_pages)

# Route to delete post (admin only)
@app.route('/admin/posts/delete/<int:post_id>', methods=['POST'])
def admin_delete_post(post_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    # Get current page from form data
    page = request.form.get('page', 1, type=int)
    
    conn = connect_db()
    cursor = conn.cursor()

    # Delete the post with the given post_id
    cursor.execute("DELETE FROM grouppost WHERE post_id = %s", (post_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_posts', page=page))

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
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Count total events
    cursor.execute("SELECT COUNT(*) AS count FROM event")
    total_events = cursor.fetchone()['count']
    total_pages = (total_events + per_page - 1) // per_page

    # Fetch paginated events with group info
    cursor.execute("""
        SELECT e.event_id, e.event_name, e.event_date, g.group_name
        FROM event e
        JOIN grouptable g ON e.group_id = g.group_id
        ORDER BY e.event_date ASC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    events = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin/events.html',
                           events=events,
                           page=page,
                           total_pages=total_pages)

# Route to delete event (admin only)
@app.route('/admin/events/delete/<int:event_id>', methods=['POST'])
def admin_delete_event(event_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    # Get current page from form data
    page = request.form.get('page', 1, type=int)
    
    conn = connect_db()
    cursor = conn.cursor()

    # Delete the event with the specified event_id
    cursor.execute("DELETE FROM event WHERE event_id = %s", (event_id,))
    
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_events', page=page))

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
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Count total ratings
    cursor.execute("SELECT COUNT(*) AS total FROM user_rating")
    total_ratings = cursor.fetchone()['total']
    total_pages = (total_ratings + per_page - 1) // per_page

    # Fetch paginated ratings
    cursor.execute("""
        SELECT ur.rater_id, ur.ratee_id, ur.rating, ur.comments, u.username
        FROM user_rating ur
        JOIN users u ON ur.ratee_id = u.userid
        ORDER BY ur.ratee_id
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    ratings = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('admin/ratings.html',
                           ratings=ratings,
                           page=page,
                           total_pages=total_pages)

# Route to delete rating (admin only)
@app.route('/admin/ratings/delete/<int:rater_id>/<int:ratee_id>', methods=['POST'])
def admin_delete_rating(rater_id, ratee_id):
    if not is_admin():
        return redirect(url_for('dashboard'))

    # Get current page from form data
    page = request.form.get('page', 1, type=int)
    
    conn = connect_db()
    cursor = conn.cursor()

    # Delete the rating given by rater_id to ratee_id
    cursor.execute("DELETE FROM user_rating WHERE rater_id = %s AND ratee_id = %s", (rater_id, ratee_id))

    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('admin_ratings', page=page))

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

# Main entry point
if __name__ == '__main__':
    # Only run in debug mode locally, not in production
    app.run(debug=os.getenv('FLASK_ENV') == 'development')