# -*- coding: utf-8 -*-
import sqlite3



class ParticipantDatabase():
    def __init__(self):
        self.connection = None
        self.cursor = None
    
    
    def connect(self, filename):
        self.connection = sqlite3.connect(filename)
        self.cursor = self.connection.cursor()
        
        #if table doesn't exist, create it
        create_table = '''
        CREATE TABLE IF NOT EXISTS Participants (
            ParticipantId VARCHAR(255) PRIMARY KEY,
            LastName VARCHAR(255) NOT NULL,
            FirstName VARCHAR(255),
            Age VARCHAR(255),
            Diagnosis VARCHAR(255)
            );
        '''
        self.cursor.execute(create_table)
        self.connection.commit()
    
    def get_all_rows(self):
        select = "SELECT * FROM Participants;"
        participants = self.cursor.execute(select).fetchall()
        return participants
        
    
    def get_participant(self, column, condition):
        select = (f"SELECT * FROM Participants WHERE {column} = {condition};" )
        participant = self.cursor.execute(select).fetchall()
        return participant
    
    
    def add_participant(self, participant_id, first_name, last_name, age, diagnosis):
        print(f"p: {type(participant_id)}, f: {type(first_name)}, l: {last_name}, a: {age}, d: {diagnosis}")
        row_str = ""
        col_str= "ParticipantId"
        row_str+="'"+participant_id +"'"
        
        if first_name != "":
            row_str += ",'" + first_name + "'"
            col_str+= ",FirstName"
        if last_name != "":
            row_str += ",'" + last_name + "'"
            col_str+= ",LastName"
        if age != "":
            row_str+= ",'" + age + "'"
            col_str+= ",Age"
        if diagnosis != "":
            row_str+= ",'" + diagnosis +"'"
            col_str+=",Diagnosis"
            
        print(row_str)
        print(col_str)
        insert = f"INSERT INTO Participants ({col_str}) VALUES ({row_str});"
                 
        try:
            self.cursor.execute(insert)
            self.connection.commit()
            return True
        except Exception as e:
            print("ERROR")
            print(e)
            return False
    
    
    def close(self):
        self.cursor.close()
        self.connection.close()
        
        




    
    
