# Store orbital inputs with each scenario

The developer refresh script writes dated CelesTrak OMM snapshots and a manifest with hashes. A scenario stores the selected OMM and its source, retrieval time, and checksum. Window generation uses that copy and a committed JPL Sun ephemeris excerpt; it does not fetch data. This keeps a replay independent of later catalogue refreshes. The window source records the propagator versions, element hash, ephemeris hash, and policy values so a changed dependency or input can be identified.
