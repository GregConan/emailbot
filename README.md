# Email Bot

## Summary

## Usage

### Command-Line Arguments

## Config File

### Example

Below is `config.ini` file including all of the necessary variable definitions:

```
[Firefox]
bin = /usr/lib/firefox/firefox-bin

[Gmail]
address = example@gmail.com
new_label = gmail-section-label

[Google.Worksheet]
id = 1234567890-iPOk6a1senbuIM8w2XG2A-12345678901
name = Title of Worksheet in Google Sheet

[Google.JSON]
service = /home/username/gcp-sheet-service-account-key.json
token = /home/username/gcp-sheet-token.json

[LinkedIn]
noreply = jobs-noreply@linkedin.com
search = https://www.linkedin.com/jobs/search/?keywords=example&sortBy=R
```