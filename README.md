# ProcessPlanner-Satisfactory-Python
 A production process planner for Satisfactory inspired by [AnthorNet/SC-ProductionPlanner](https://github.com/AnthorNet/SC-ProductionPlanner) - implemented in Python

 Acting as a proof of concept for implementing an in-game production process planner in lua for a smart factory using the [Ficsit Networks](https://github.com/CoderDE/FicsIt-Networks) mod for Satisfactory

## Usage
Run the python script to start the Dash interactive UI: `python planner_ui.py`

Interactive web based UI only for testing and proof of concept - only plans for 1 item per minute of requested item

Production buildings and edges don't account for maximum overclocking or maximum conveyor/pipe throughput - so less overall nodes, this should actually be easier to work with when it comes to the actual lua implementation within Satisfactory
