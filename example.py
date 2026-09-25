"""Sample: fastest journey from Marton Public School to the Queen Victoria Building."""

from datetime import datetime

from main import SYDNEY_TZ, fastest_journey

MARTON_PUBLIC_SCHOOL = "GANSW711624184"  # 107 Kingswood Road, Engadine NSW 2233
QVB = "GANSW706029353"  # 429-481 George Street, Sydney NSW 2000

journey = fastest_journey(
    MARTON_PUBLIC_SCHOOL,
    QVB,
    arrive_by=datetime(2026, 9, 28, 9, 0, tzinfo=SYDNEY_TZ),
)

if journey is None:
    print("No journey found")
else:
    print(f"From building:    {journey.depart_building_id} "
          f"({journey.depart_latitude}, {journey.depart_longitude})")
    print(f"Depart:           {journey.departure:%a %d %b %H:%M}")
    print(f"Arrive:           {journey.arrival:%a %d %b %H:%M}")
    print(f"Journey time:     {journey.journey_minutes} min")
    print(f"Walking time:     {journey.walking_minutes} min")
    print(f"Walking distance: {journey.walking_distance_m} m")
    print(f"Transports:       {journey.transports}")
    print(f"has_bus={journey.has_bus} has_train={journey.has_train} "
          f"has_ferry={journey.has_ferry} has_tram={journey.has_tram}")
