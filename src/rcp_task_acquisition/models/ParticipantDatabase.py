# -*- coding: utf-8 -*-
import sqlite3



class ParticipantDatabase():
    def __init__(self):
        self.connection = None
        self.cursor = None
    
    def connect(self, filename):
        self.conneciton = sqlite3.connect(filename)
        self.cursor = self.connection.cursor()
        
        #if table doesn't exist, create it
        create_table = '''
        CREATE TABLE IF NOT EXISTS Participants (
            ParticipantId int PRIMARY KEY,
            LastName varchar(255),
            FirstName varchar(255),
            Type varchar(255)
            );
        '''
        self.cursor.execute(create_table)
        
        
    def close(self):
        self.connection.close()
    
    
