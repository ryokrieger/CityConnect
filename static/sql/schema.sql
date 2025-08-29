CREATE DATABASE cityconnect;

USE cityconnect;

CREATE TABLE City (
    city_code INT PRIMARY KEY,
    city_name VARCHAR(50),
    country VARCHAR(50)
);

CREATE TABLE Neighborhood (
    postal_code INT PRIMARY KEY,
    area_name VARCHAR(100),
    city_code INT,
    FOREIGN KEY (city_code) REFERENCES City(city_code)
);

CREATE TABLE User (
    userID INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE,
    email VARCHAR(100) UNIQUE,
    gender ENUM('Male', 'Female', 'Other'),
    password VARCHAR(100) NOT NULL,
    city_code INT,
    postal_code INT,
    is_admin BOOLEAN DEFAULT FALSE,
    is_restricted BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (city_code) REFERENCES City(city_code),
    FOREIGN KEY (postal_code) REFERENCES Neighborhood(postal_code)
);

CREATE TABLE Interest (
    interest_ID INT PRIMARY KEY AUTO_INCREMENT,
    interest_name VARCHAR(100),
    category VARCHAR(50)
);

CREATE TABLE User_Interest (
    userID INT,
    interest_ID INT,
    PRIMARY KEY (userID, interest_ID),
    FOREIGN KEY (userID) REFERENCES User(userID) ON DELETE CASCADE,
    FOREIGN KEY (interest_ID) REFERENCES Interest(interest_ID) ON DELETE CASCADE
);

CREATE TABLE Friendship (
    user1_ID INT,
    user2_ID INT,
    PRIMARY KEY (user1_ID, user2_ID),
    FOREIGN KEY (user1_ID) REFERENCES User(userID) ON DELETE CASCADE,
    FOREIGN KEY (user2_ID) REFERENCES User(userID) ON DELETE CASCADE
);

CREATE TABLE FriendRequest (
    request_id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT,
    receiver_id INT,
    status ENUM('pending', 'accepted', 'declined') DEFAULT 'pending',
    request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES User(userID) ON DELETE CASCADE,
    FOREIGN KEY (receiver_id) REFERENCES User(userID) ON DELETE CASCADE
);

CREATE TABLE Message (
    message_ID INT PRIMARY KEY AUTO_INCREMENT,
    sender_ID INT,
    receiver_ID INT,
    content TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_ID) REFERENCES User(userID) ON DELETE CASCADE,
    FOREIGN KEY (receiver_ID) REFERENCES User(userID) ON DELETE CASCADE
);

CREATE TABLE  GroupTable (
    group_ID INT PRIMARY KEY AUTO_INCREMENT,
    group_name VARCHAR(100),
    description TEXT
);

CREATE TABLE Group_Interest (
    group_ID INT,
    interest_ID INT,
    PRIMARY KEY (group_ID, interest_ID),
    FOREIGN KEY (group_ID) REFERENCES GroupTable(group_ID) ON DELETE CASCADE,
    FOREIGN KEY (interest_ID) REFERENCES Interest(interest_ID) ON DELETE CASCADE
);

CREATE TABLE User_Group (
    userID INT,
    group_ID INT,
    PRIMARY KEY (userID, group_ID),
    FOREIGN KEY (userID) REFERENCES User(userID) ON DELETE CASCADE,
    FOREIGN KEY (group_ID) REFERENCES GroupTable(group_ID) ON DELETE CASCADE
);

CREATE TABLE GroupPost (
    post_ID INT PRIMARY KEY AUTO_INCREMENT,
    group_ID INT,
    userID INT,
    content TEXT,
    post_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_ID) REFERENCES GroupTable(group_ID) ON DELETE CASCADE,
    FOREIGN KEY (userID) REFERENCES User(userID) ON DELETE CASCADE
);

CREATE TABLE GroupComment (
    comment_ID INT PRIMARY KEY AUTO_INCREMENT,
    post_ID INT,
    userID INT,
    content TEXT,
    comment_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_ID) REFERENCES GroupPost(post_ID) ON DELETE CASCADE,
    FOREIGN KEY (userID) REFERENCES User(userID) ON DELETE CASCADE
);

CREATE TABLE Event (
    event_ID INT PRIMARY KEY AUTO_INCREMENT,
    event_name VARCHAR(100),
    event_date DATE,
    group_ID INT,
    event_description TEXT,
    event_time TIME,
    creator_ID INT,
    city_code INT,
    postal_code INT,
    FOREIGN KEY (group_ID) REFERENCES GroupTable(group_ID) ON DELETE CASCADE,
    FOREIGN KEY (creator_ID) REFERENCES User(userID),
    FOREIGN KEY (city_code) REFERENCES City(city_code),
    FOREIGN KEY (postal_code) REFERENCES Neighborhood(postal_code)
);

CREATE TABLE event_participation (
    userID INT,
    event_ID INT,
    PRIMARY KEY (userID, event_ID),
    FOREIGN KEY (userID) REFERENCES User(userID) ON DELETE CASCADE,
    FOREIGN KEY (event_ID) REFERENCES Event(event_ID) ON DELETE CASCADE
);

CREATE TABLE User_Rating (
    rater_ID INT,
    ratee_ID INT,
    rating INT CHECK (rating BETWEEN 1 AND 5),
    comments TEXT,
    PRIMARY KEY (rater_ID, ratee_ID),
    FOREIGN KEY (rater_ID) REFERENCES User(userID),
    FOREIGN KEY (ratee_ID) REFERENCES User(userID)
);