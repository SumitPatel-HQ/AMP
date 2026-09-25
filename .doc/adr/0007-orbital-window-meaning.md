# Orbital windows are visible time windows

An orbital observation window spans the time a target is inside the configured field of regard. The window is long enough for the request's duration, and the planner chooses the action's start inside it. For an optical mission, the Sun must meet the configured elevation at the pass peak. We chose this meaning over a ground observer's horizon pass because a horizon pass would admit targets outside the imager's pointing limit. The model treats pointing as agile within the field of regard; it does not yet model slew or settling time.
