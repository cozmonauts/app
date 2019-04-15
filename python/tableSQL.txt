CREATE TABLE Students (
    	Studentid int NOT NULL AUTO_INCREMENT,
    	Name varchar(255) NOT NULL,
    	Image text NOT NULL,
    	Date_seen DATETIME NOT NULL DEFAULT NOW(),
    	PRIMARY KEY (Studentid)	
    );