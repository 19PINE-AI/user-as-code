from dataclasses import dataclass, field
from datetime import date, time

@dataclass
class JobHistory:
    title: str
    employer: str = ""
    date_ended: date = None
    notes: list[str] = field(default_factory=list)

@dataclass
class Business:
    name: str
    owner: str
    industry: str
    status: str
    location_description: str = ""
    features: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

@dataclass
class Competition:
    title: str
    participant: str
    result: str
    date_event: date = None
    age_at_time: int = None
    piece_performed: str = ""
    notes: list[str] = field(default_factory=list)

@dataclass
class Travel:
    person: str
    destination: str
    date_visited: date = None
    frequency: str = ""
    notes: list[str] = field(default_factory=list)

@dataclass
class Session:
    session_id: str
    timestamp: date
    time_of_day: str
    participants: list[str]
    notes: list[str] = field(default_factory=list)

@dataclass
class DanceProject:
    lead: str
    type: str
    scheduled_date: date = None
    notes: list[str] = field(default_factory=list)

@dataclass
class Person:
    name: str
    passions: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    jobs: list[JobHistory] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

# --- Instances ---

# PERSON: JON
jon = Person(
    name="Jon",
    passions=["Dancing (Contemporary, Hip-hop)", "Sharing dance with others"],
    skills=["Choreography", "Contemporary dance", "Hip-hop"],
    notes=[
        "Plans to start his own business",
        "Jon considers dancing his escape and his passion",
        "Interested in dancing since he was a child",
        "Wants to teach others the joy of dancing",
        "Believes contemporary dance is expressive and powerful",
        "Jon's favorite dance style is contemporary",
        "Looking forward to meeting Gina on Jan 27, 2023",
        "Feeling excited",
        "Wants to show Gina his dance moves",
        "Jon describes his journey with dance as 'bumpy'",
        "Determined to make his dance career/business work",
        "Working on new dance routines as of Feb 4, 2023",
        "Has a community he calls his 'dance fam'",
        "Jon states he will not give up"
    ]
)
jon.jobs.append(JobHistory(title="Banker", date_ended=date(2023, 1, 19), notes=["Lost job on Jan 19, 2023"]))

# PERSON: GINA
gina = Person(
    name="Gina",
    passions=["Dance (stress relief)", "Contemporary dance"],
    notes=[
        "Expressed sympathy to Jon regarding his job loss",
        "Believes contemporary dance is expressive, graceful, and speaks to her",
        "Likes contemporary dance",
        "Wants to explore new dance moves",
        "Available to meet Jon on Jan 27, 2023",
        "Has never visited Paris",
        "Life has been hectic recently",
        "Finds taking risks scary but rewarding",
        "Believes Jon has drive, skills, passion, and talent",
        "Refers to Jon as 'buddy'",
        "Stated she is there for Jon no matter what"
    ]
)
gina.jobs.append(JobHistory(title="Courier", employer="Door Dash", date_ended=date(2023, 1, 1), notes=["Lost job in Jan 2023"]))

# BUSINESSES
jon_studio = Business(
    name="Jon's Dance Studio",
    owner="Jon",
    industry="Dance Studio",
    status="Establishing / Searching for location",
    location_description="Downtown area (potential), ideally by the water",
    features=["Marley flooring (planned for grip/durability)", "Natural light"],
    notes=[
        "Jon is searching for the ideal location; describes it as 'quite a journey'",
        "Needs a floor with a specific 'bounce' for safety",
        "Jon found a potential downtown spot with great light around Jan 29, 2023",
        "Gina thinks the downtown spot is a 'nice spot'",
        "Jon needs to check size and floor quality"
    ]
)

gina_store = Business(
    name="Gina's Clothing Store",
    owner="Gina",
    industry="Apparel",
    status="Active / Expanding",
    location_description="Cozy and inviting interior",
    features=["Chandelier (glam feel)", "Comfortable furniture", "Trendy pieces"],
    goals=["Grow business", "Get closer to customers", "Create a 'cool oasis' experience"],
    notes=[
        "Launched an ad campaign recently (Jan 2023)",
        "Gina designed the interior herself",
        "Wholesaler replied 'yes' on Feb 1, 2023",
        "Gina feels 'over the moon' about the wholesaler reply",
        "Jon believes the store space looks 'perfect'"
    ]
)

# COMPETITIONS & PERFORMANCES
jon_crew_win = Competition(
    title="Local Dance Competition",
    participant="Jon / Dance Crew",
    result="First Place",
    date_event=date(2022, 1, 1), # Year 2022
    notes=["Jon felt amazing performing on stage"]
)

gina_regional_win = Competition(
    title="Regional Dance Competition",
    participant="Gina / Dance Team",
    result="First Place",
    age_at_time=15,
    piece_performed="Finding Freedom",
    notes=["Piece described as emotional and powerful", "Gina felt a sense of accomplishment"]
)

upcoming_competition = Competition(
    title="Local Dance Competition",
    participant="Jon",
    result="TBD",
    date_event=date(2023, 3, 1), # March 2023
    notes=["Jon is 'super stoked'; views it as a chance to show skills and get 'props'"]
)

# SESSIONS & EVENTS
sessions = [
    Session("session_1", date(2023, 1, 20), "4:04 pm", ["Gina", "Jon"], ["Jon and Gina scheduled a meeting for Jan 27, 2023", "Jon shared a picture with Gina"]),
    Session("session_2", date(2023, 1, 29), "2:32 pm", ["Gina", "Jon"], ["Gina and Jon had not seen each other for a long time prior", "Jon visited Paris yesterday"]),
    Session("session_3", date(2023, 2, 1), "12:48 am", ["Gina", "Jon"], ["Gina sent Jon a picture of a location and a peek at the design"]),
    Session("session_4", date(2023, 2, 4), "10:43 am", ["Gina", "Jon"], ["Jon is preparing for a March competition"]),
    Session("session_5", date(2023, 2, 8), "9:32 am", ["Gina", "Jon"], ["Ongoing communication"])
]

festival_perf = DanceProject(
    lead="Jon",
    type="Festival Performance",
    scheduled_date=date(2023, 2, 1), # Feb 2023
    notes=["Jon and group rehearsing after work", "Group described as skillful and graceful", "Jon is finishing choreography"]
)

meeting_jan_27 = Session(
    session_id="meeting_1",
    timestamp=date(2023, 1, 27),
    time_of_day="TBD",
    participants=["Gina", "Jon"],
    notes=["Jon proposed attending a dance class together", "Jon believes it would be fun"]
)

# TRAVEL
paris_trip = Travel("Jon", "Paris", date(2023, 1, 28), notes=["Jon thought it was 'sooo cool'"])
rome_trip = Travel("Gina", "Rome", frequency="Exactly one time")

# COLLECTIONS
people = [jon, gina]
businesses = [jon_studio, gina_store]
competitions = [jon_crew_win, gina_regional_win, upcoming_competition]
events = [festival_perf, meeting_jan_27]
travel_history = [paris_trip, rome_trip]

# RELATIONSHIP NOTES (Aggregated)
relationship_facts = [
    "Jon and Gina have a supportive relationship",
    "Gina encourages Jon to believe in himself and take breaks",
    "Jon believes he can handle anything with Gina's support",
    "Gina believes they both have already accomplished a lot",
    "Jon encourages Gina to 'hang in there'",
    "Mutual support in chasing dreams and business goals"
]
