I want you to pull in the cxxopts dependency. First, try pulling it in through pixi if possible and add it to the cmake via `add_package`. If it's not available via pixi, add it via CPM.

Then, I want you to link the dependency to MyApp and incorporate it into the main.cpp file. Just a stub implementation by adding a few cli args to MyApp.

For testing, just ensure it builds and runs as expected.
