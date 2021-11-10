import datetime
import os.path
import googlemaps

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]
BUFFER_TIME_CALENDAR = "Buffer time"
ID_PREFIX = "Tied to event: "
PREFERRED_TRANSPORT = "DRIVING"
# TRANSPORT_MODES = ["DRIVING", "WALKING", "BICYCLING", "TRANSIT"]
TRANSPORTS = ["driving"]
EMOJI = {"driving": "🚗", "WALKING": "🚶", "BICYCLING": "🚴", "TRANSIT": "🚆"}


def main():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    service = build("calendar", "v3", credentials=creds)

    # get all calendars and create calendar BUFFER_TIME_CALENDAR
    calendars = list_calendars(service)
    if BUFFER_TIME_CALENDAR not in calendars:
        calendars[BUFFER_TIME_CALENDAR] = create_buffer_time_calendar(service)

    # get already created buffer events linked to main events
    start = datetime.datetime.now().isoformat() + "Z"
    end = start + datetime.timedaelta(days=13-start.weekday())
    end = end.isoformat() + "Z"

    buffer_id = calendars[BUFFER_TIME_CALENDAR]["id"]
    b_events_result = (
        service.events()
        .list(
            calendarId=buffer_id,
            timeMin=start,
            timeMax=end,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    b_events = b_events_result.get("items", [])

    buffers = dict()
    for event in b_events:
        main_event_id = [
            line.split(': ')[1]
            for line in event["description"].split("\n")
            if line.startswith(ID_PREFIX)
        ][0]
        buffers[main_event_id] = event

    # Call the Calendar API
    now = (
        datetime.datetime.utcnow().isoformat() + "Z"
    )  # 'Z' indicates UTC time
    print("Getting the upcoming 10 events")
    # start = datetime.date.today()
    # end = start + datetime.timedaelta(days=13-start.weekday())
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now,
            maxResults=10,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])

    if not events:
        print("No upcoming events found.")

    with open("key.txt") as f:
        google_maps_key = f.read()

    google_maps_client = googlemaps.Client(google_maps_key)
    origins = ["Radmanovačka ul. 6f, 10000, Zagreb"]
    for event in events:
        start_time = event["start"].get("dateTime")
        if start_time is None:
            print("event has no start time")
            continue

        start_time = datetime.datetime.fromisoformat(start_time).timestamp()
        # TODO: convert start time to integer
        location = event.get("location")
        if location is None:
            print("event has no location")
            continue

        description_list = []
        # description.append(
        #     f"Commute time from {old_location} to {new_location}."
        # )

        for transport in TRANSPORTS:
            distance_matrix = google_maps_client.distance_matrix(
                origins=origins,
                destinations=[location],
                mode=transport,
                arrival_time=start_time,
            )
            duration = distance_matrix["rows"][0]["elements"][0]["duration"]
            duration_value = duration["value"]
            duration_text = duration["text"]
            description_list.append(
                EMOJI[transport] + " " + transport + " " + duration_text
            )

            if transport == PREFERRED_TRANSPORT:
                summary = description_list[-1]
                print(f"transport: {transport}")
                description_list[-1] = "[x] " + description_list[-1]
            else:
                description_list[-1] = "[ ] " + description_list[-1]

        event_id = event["id"]
        description_list.append(f"{ID_PREFIX}{event_id}")
        description = "\n".join(description_list)

        create_calendar_event(
            service=service,
            buffer_time_calendar_id=calendars[BUFFER_TIME_CALENDAR],
            summary=summary,
            description=description,
            start_time=datetime.datetime.fromtimestamp(start_time),
            end_time=datetime.datetime.fromtimestamp(start_time + duration_value),
            recurrence="",
        )


def list_calendars(service):
    # for choosing which calendar should be on the watch list you have to use summaryOverride
    # for looking up BUFFER_TIME_CALENDAR in calendars you have to use summary
    calendars = {}
    page_token = None
    while True:
        calendar_list = (
            service.calendarList().list(pageToken=page_token).execute()
        )
        for calendar in calendar_list["items"]:
            name = calendar.get("summaryOverride", calendar.get("summary"))
            id_ = calendar.get("id")
            calendars[name] = calendar.get("id")
        page_token = calendar_list.get("nextPageToken")
        if not page_token:
            break

    return calendars


def create_buffer_time_calendar(service):
    calendar = {
        "summary": BUFFER_TIME_CALENDAR,
    }
    created_calendar = service.calendars().insert(body=calendar).execute()
    return created_calendar["id"]


def create_calendar_event(
    service,
    buffer_time_calendar_id,
    summary,
    description,
    start_time,
    end_time,
    recurrence,
):
    start = {"dateTime": start_time}
    end = {
        "dateTime": end_time,
        # "timeZone": "America/Los_Angeles",
    }
    buffer_time_event = {
        "summary": summary,
        # "location": "",
        "description": description,
        "start": start,
        "end": end,
        # "recurrence": recurrence,
    }
    print('hello')
    buffer_time_event = (
        service.events().insert(calendarId=calendar_id, body=event).execute()
    )
    print("Event created: %s" % (buffer_time_event.get("htmlLink")))


if __name__ == "__main__":
    main()
