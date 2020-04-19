import csv
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

db = scoped_session(sessionmaker(bind=engine))



#Table Names for reference
#   - accounts(id, username, password, email)
#   - books(id, ISBN, title, author, publish_data)
#   - review(id, useR_id, book_id, book_score)

def main():
    f = open("books.csv")
    reader = csv.reader(f)
    for isbn, title, author, year in reader:
        db.execute("INSERT INTO books (ISBN, title, author, publish_date) VALUES (:ISBN, :title, :author, :publish_date)",
                   {"ISBN": isbn, "title": title, "author": author, "publish_date": year})
        print(f"Added {title} by {author} to database")
    db.commit()
if __name__ == "__main__":
    main()
           
