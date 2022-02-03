from flask import Flask, render_template, url_for, redirect, make_response
from flask import request
from my_types.types import Team, Player, Game
import boto3
import csv
import mysql.connector
import os


application = Flask(__name__)
ALLOWED_EXTENSIONS = ["csv"]
UPLOAD_FOLDER = "./temp"
application.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

def sanitize(string_in):
    return string_in.replace("\"", "").strip()

def allowed_file(filename):
    return "." in filename and \
        filename.split(".")[:-1].lower() in ALLOWED_EXTENSIONS

@application.route("/")
def index():
    return render_template("index.html", title="Interview Questions",
        header="Queries")

@application.route("/load_csv", methods=["GET", "POST"])
def load_csv():
    bucket = "nmedovich-interview"
    file_name = ""
    s3_upload = True
    # Load flat file from S3
    if request.method == "GET":
        file_name = "mlb_players.csv"
    else:
        print(request.files)
        # Empty file sent
        if "file" not in request.files:
            res = make_response('No "file" body detected', 200)
            res.mimetype = "text/plain"
            return res
        file = request.files["file"]
        # No filename, so no file sent
        if not file.file_name:
            res = make_response('No file selected', 200)
            res.mimetype = "text/plain"
            return res
        # Valid filetype filename exists
        if file and allowed_file(file.filename):
            s3_upload = False
            file.save(os.path.join(application.config["UPLOAD_FOLDER"], filename))
            file_name = os.path.join(application.config["UPLOAD_FOLDER"], filename)
        # Overrise, and use S3 bucket
        if "file_name" in request.args:
            file_name = request.args["file_name"]
    lines = None
    # Use S3 File
    if s3_upload:
        s3 = boto3.client("s3")
        s3_obj = s3.get_object(Bucket=bucket, Key=file_name)["Body"]
        lines = s3_obj.read().decode('utf-8').splitlines(True)
    # Use Flat file or Uploaded file
    else:
        lines = open(file_name, "r")
    # Ignoring Headers
    first_line = True
    teams = []
    players = []
    for row in csv.reader(lines):
        if not first_line:
            try:
                # Prep Team Object
                team_name = sanitize(row[1])
                team = Team(team_name)
                teams.append(team)
                # Prep Player Object
                height = 0
                weight = 0
                age = 0.0
                name = sanitize(row[0])
                height = row[3]
                weight = sanitize(row[4])
                if not weight:
                    weight = None
                age = row[5]
                position = sanitize(row[2])
                team_name = sanitize(row[1])
                player = Player(
                    name, height, weight, age, position, team_name
                )
                players.append(player)
            except IndexError:
                break
        else:
            first_line = False
    # Set up database connector to pass to helper functions
    host = "0.0.0.0"
    user = "root"
    database = "mlb_players"
    password = ""
    with open("secret.txt", "r") as f_in:
        password = f_in.read().split("\n")[0]
    db_conn = mysql.connector.connect(
        host = host,
        user = user,
        password = password,
        database = database
    )
    # Add teams to table if they don't exist, ignore if they do
    Team.load_teams(teams, db_conn)
    # Retrieve teams and team IDs for Player objects
    teams_dict = Team.get_teams(db_conn)
    for player in players:
        player.set_team_id(teams_dict[player.team_name])
    # Add players to table (ignoring existant records for testing)
    Player.load_players(players, db_conn)
    # We're finally done with loading the databases
    res = make_response("Successfully loaded", 200)
    res.mimetype = "text/plain"
    return res

