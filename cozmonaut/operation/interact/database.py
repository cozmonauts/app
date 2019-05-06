#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

import mysql.connector
from datetime import datetime

#Connect to SQL Server
connection = mysql.connector.connect(
        host="localhost",
        user="root",
        passwd="password",
        database="Cozmo"
)

dateTime = datetime.now()
dateFormat = dateTime.strftime('%Y-%m-%d %H:%M:%S')
myCursor = connection.cursor()

# Retrieve and return 'Studentid' & 'imageID' pairs from db
def loadStudents():
    selectQuery = """SELECT Studentid, Image FROM Students"""
    myCursor.execute(selectQuery)
    retrieveAll = myCursor.fetchall()

    if retrieveAll is not None:
        for studentPairs in retrieveAll:
            #print(studentPairs)
            return (studentPairs)

# If studentID not seen by cosmo, insert new student with their name and imageID;
# Returns 'Studentid'
def insertNewStudent(studentName, imageID):

    insertStudent = """INSERT INTO Students(Name, Image) VALUES('%s', '%s')""" % (studentName, imageID)
    myCursor.execute(insertStudent)
    connection.commit()
    print("Insertion was a success...")

    returnID = """SELECT Studentid FROM Students WHERE Name = '%s' AND Image = '%s'""" % (studentName, imageID)
    myCursor.execute(returnID)
    fetchID = myCursor.fetchall()
    if fetchID is not None:
       for x in fetchID:
            print("Returning Student's ID..")
            #print (x[0]) #will return studentID number ? switch orint with return
            return(x[0])

# If studentID seen by cozmo before, update the Date_seen
def checkForStudent(studentID):

    checkUser = """SELECT Studentid FROM Students WHERE Studentid = '%s'""" % (studentID)
    myCursor.execute(checkUser)
    check = myCursor.fetchone()

    if check is not None:
        updateExistingUser = """UPDATE Students SET Date_seen = '%s' WHERE Image = '%s'""" % (dateFormat, studentID)
        myCursor.execute(updateExistingUser)
        connection.commit() #Needed To Update Database
        print("Studentid has been seen, updating 'Date_seen' Column;")

# Delete Student based on their 'Studentid'
def deleteStudent(studentID):

    selectQuery = """SELECT Studentid FROM Students WHERE Studentid = '%s'""" % (studentID)
    myCursor.execute(selectQuery)
    studID = myCursor.fetchone()

    if studID is not None:
        delete = """DELETE FROM Students WHERE Studentid = '%s'""" % (studentID)
        myCursor.execute(delete)
        print("Student ID =",studID[0], "was deleted from the Database")
        connection.commit()

    if studID is None:
        print("Student ID =",studentID,"not in the current Database")

# Return only 'Studentid'
def listStudentIDs():
    selectQuery = """SELECT Studentid FROM Students"""
    myCursor.execute(selectQuery)
    retrieveAll = myCursor.fetchall()

    if retrieveAll is not None:
        for studID in retrieveAll:
            #print(studID[0])
            return (studentPairs[0])

# Based on 'Studentid' list the name and date last seen of that student
def determineStudent(studentID):
    select = """SELECT Name, Date_seen FROM Students WHERE StudentID = '%s'""" % (studentID)
    myCursor.execute(select)
    obtainName = myCursor.fetchall()
    if obtainName is not None:
        for x , y in obtainName:
            print("Student with ID = ",studentID, "is ", x, "and date last seen is", y)
            return x, y  # NOTE(tyler): Return both the name and the date last seen

#Return name of student who was seen most recently
def returnStudentName():
    select = """SELECT Name FROM Students WHERE Date_seen = (SELECT MAX(Date_seen) FROM Students)"""
    myCursor.execute(select)
    returnName = myCursor.fetchall()
    if returnName is not None:
        for x in returnName:
            #print(x[0])
            return(x[0])

#store face as base 64 text string? = 'text' data type(pretty large numbers)
if __name__ == "__main__":

    #insertNewStudent("NEW5", 1000)
    #checkForStudent(3)
    #loadStudents()
    #deleteStudent(2)
    #listStudentIDs()
    #determineStudent(1)

    myCursor.close()
    connection.close()
