House Tracker
====

## Config

```ini
ServiceHealthNotification = yes
ServiceHealthNotificationFrequency = 6
ServiceHealthNotificationRecipients = email1,email2,email3 // As many as you want
NotificationFrequency = 15
NotificationRecipients = email1,email2 // As many as you want
MailApiToken = <Google App Password>
SenderEmail = <>@gmail.com // Gmail Account 
```
Set up Google app passwords: https://www.lifewire.com/get-a-password-to-access-gmail-by-pop-imap-2-1171882

## Execution

Environment Setup:  
Use `Python >= 3.8`  
Run `pip install -r requirements.txt`

Clone this repo and cd into the directory
```bash
git clone git@github.com:anti-mony/MartinHouseTracker.git
cd MartinHouseTracker
```

Now to execute run, 

```sh
nohup python Tracker.py &
```  
This will run the service in backgroud, you can see the log files to see what's up with the app.

Get list of running backgrond jobs   
```sh
jobs -l
```
This will return a list of jobs running in the backgroud. This will also contain a process id (number).

To stop the app run, use process id retrieved using the command mentionsed above:
```bash
kill <process_id>
```


