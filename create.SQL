CREATE TABLE accounts(
	id serial PRIMARY KEY,
	username VARCHAR (20) UNIQUE NOT NULL,
	password VARCHAR (20) NOT NULL,
	email VARCHAR (355) UNIQUE NOT NULL
);

CREATE TABLE books (
	id serial PRIMARY KEY,
	ISBN VARCHAR(13) NOT NULL,
	title VARCHAR(50) NOT NULL,
	author VARCHAR(50) NOT NULL,
	publish_date SMALLINT NOT NULL,
);

CREATE TABLE review(
	id SERIAL PRIMARY KEY,
	user_id INTEGER REFERENCES accounts(id),
	book_id INTEGER REFERENCES books(id),
	book_score INTEGER DEFAULT 0,
	book_review TEXT
);