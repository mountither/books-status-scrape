
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import json
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from dotenv import load_dotenv
load_dotenv()

# headers = {
#     "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36 Edg/85.0.564.51"
# }

#TODO 1. provide more info about book status change in email (what changed and price). 

class AccessWebsite:

    def __init__(self, url):
    
        self.driver = webdriver.Firefox(executable_path=GeckoDriverManager().install())
        self.driver.get(url)
        self.currentBooks = {}
        self.previousBooks = {}

        # open or dump file locally 
        self.outputFile = "books_output.json"

        # save in AWS documentDB via mongoDB
        #self.client = pymongo.MongoClient(os.getenv("MONGO_URL"))
        
        # connect to the database
        #self.db = self.client.books

        # access the required collection for this script 
        #self.collection = self.db.bookStatus

    def Login(self, email, passw):

        emailLog = self.driver.find_element_by_xpath("//input[@id='loginEmail']")
        passLog = self.driver.find_element_by_xpath("//input[@id='loginPassword']")

        emailLog.send_keys(email)
        passLog.send_keys(passw)

        loginBtn = self.driver.find_element_by_xpath( "//button[@class='form-control btn btn-success']")
        loginBtn.click()
    
    def AttemptToNavigate(self):
        try:

            tagWL = "/html[1]/body[1]/div[6]/div[1]/h1[1]/small[1]"

            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, tagWL)))

            booksInWL = self.__getAmountInWishlist(tagWL)
            
            self.__getBooksByTag(booksInWL)

            self.__openJSONFileWithPrevList()


            recentChange = self.__checkAnyRecentChangeToList()

            isChanged, booksCh, textCh, priceCh = self.__compareDictPrevCurrent(recentChange)

            if (isChanged):
                alert = Alert()
                alert.composeEmail(booksInWL, booksCh, textCh, priceCh)
                alert.sendEmail()

            self.__dumpJSONWithCurrentList()
            self.driver.quit()

        except TimeoutException:
            print("Loading is taking too long")


    def __getAmountInWishlist(self, tagWithAmount):

        tagWithBookAmt = self.driver.find_element_by_xpath(tagWithAmount).text
        amt = re.findall(r"(\d+)", tagWithBookAmt)
        return amt


    def __getBooksByTag(self, amtOfBooks):

        for x in range(1,int(amtOfBooks[0]) + 1):

            xpathStatus = "/html[1]/body[1]/div[6]/div[1]/div[1]/div[2]/div["
            xpathStatus += str(x)
            xpathStatus +="]/div[1]/div[1]/div[1]/div[2]/table[1]/tr[1]/td[1]/span[1]"

            xpathTitle = "/html[1]/body[1]/div[6]/div[1]/div[1]/div[2]/div["
            xpathTitle += str(x)
            xpathTitle += "]/div[1]/div[1]/div[1]/div[2]/h4[1]/a[1]"

            # "/html[1]/body[1]/div[5]/div[1]/div[1]/div[2]/div[1]/div[1]/div[1]/div[1]/div[2]/table[1]/tr[1]/td[1]/strong[1]"
            # "/html[1]/body[1]/div[5]/div[1]/div[1]/div[2]/div[2]/div[1]/div[1]/div[1]/div[2]/table[1]/tr[1]/td[1]/strong[1]"

            if (self.driver.find_element_by_xpath(xpathStatus).text == "Used from"):
                xpathPrice = "/html[1]/body[1]/div[6]/div[1]/div[1]/div[2]/div["
                xpathPrice += str(x)
                xpathPrice += "]/div[1]/div[1]/div[1]/div[2]/table[1]/tr[1]/td[1]/strong[1]"
                sendPrice = self.driver.find_element_by_xpath(xpathPrice).text 
            else:
                sendPrice = ""

            self.currentBooks[self.driver.find_element_by_xpath(xpathTitle).text] = [self.driver.find_element_by_xpath(xpathStatus).text, 
                                                                                    sendPrice]
            
        
    

    def __openJSONFileWithPrevList(self):
        with open(self.outputFile) as rf:
            self.previousBooks = json.load(rf)

      

    def __dumpJSONWithCurrentList(self):
         with open(self.outputFile, 'w') as wf:
                json.dump(self.currentBooks, wf, indent=4)


    def __checkAnyRecentChangeToList(self):

        removedFromWL = self.previousBooks.keys() - self.currentBooks
        addedToWL = self.currentBooks.keys() - self.previousBooks

        if (len(removedFromWL) > 0):
            changeToWL = removedFromWL
        elif (len(addedToWL) > 0):
            changeToWL = addedToWL
        else:
            changeToWL = ""

        return changeToWL

    def __compareDictPrevCurrent(self, changesToWL):

        alertChange = False
        booksChange = []
        statusChange = []
        priceChange = []

        for keys in self.currentBooks:
            if keys not in changesToWL:
                if (self.currentBooks[keys][0] != self.previousBooks[keys][0]):
                    alertChange = True
                    booksChange.append(keys + " - Status Change")
                    statusChange.append(keys + ": " + self.previousBooks[keys][0] + " --> " + self.currentBooks[keys][0])

                if(self.currentBooks[keys][1] != self.previousBooks[keys][1]):
                    alertChange = True
                    booksChange.append(keys + " - Price Change")
                    priceChange.append(keys + ": " + self.previousBooks[keys][1] + " --> " + self.currentBooks[keys][1])
                    
        return alertChange, booksChange, statusChange, priceChange

    

class Alert:

    def __init__(self):

        self.server = smtplib.SMTP(os.getenv("SMTP_HOST"), os.getenv("SMTP_PORT"))
        self.eFrom = os.getenv("EMAIL_ADDR")
        self.eTo = [os.getenv("EMAIL1_TO")]

    def composeEmail(self, bookAmt, effectedBooks, txtChange, priceChange):
        bookAmt = str(bookAmt[0])
        linebreak = "<br>"

        self.msg = MIMEMultipart('alternative')
        self.msg['Subject'] = "Book Status Changed"

        html = f"""
            <html>
                <head><head>
                <body>
                    <h1>Alert! Book activity detected</h1>{linebreak}
                    <h3 style="text-align:center;color:maroon;"> The books that changed status: </h3>
                    <h4 style="text-align:center;">{linebreak}{linebreak.join(effectedBooks)}<h4>
                    <h3 style="text-align:center;color:maroon;">The status changes:</h3> 
                        <h4 style="text-align:center;">{linebreak}{linebreak.join(txtChange)}</h4>
                    <h3 style="text-align:center;color:maroon;">Price Changes:</h3>
                        <h4 style="text-align:center;">{linebreak}{linebreak.join(priceChange)}</h4>
                    <h3 style="text-align:center;color:maroon;">The amount of books in Wishlist:</h3>
                        <h4 style="text-align:center;">{bookAmt}</h4>
                </body>
            </html>
            """

        record = MIMEText(html, 'html')

        self.msg.attach(record)


    def sendEmail(self):
       
        self.server.starttls()

        
        self.server.login(self.eFrom, os.getenv("EMAIL_PWD"))
        self.server.helo()

        self.server.sendmail(self.eFrom, self.eTo, self.msg.as_string())

        self.server.quit()




web = AccessWebsite(os.getenv("URL_LINK"))

web.Login(os.getenv("BWB_EMAIL") , os.getenv("BWB_PWD"))

web.AttemptToNavigate()