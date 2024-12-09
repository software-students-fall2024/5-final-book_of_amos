# Final Project 

An exercise to put to practice software development teamwork, database integration, containers, deployment, and CI/CD pipelines.

## Requirements

This is an open-ended exercise for you to show your mastery of software engineering, with some specific requirements:

- Your software must be composed of at least 2 different subsystems
- One of those subsystems must be a MongoDB database.
- The other subsystem(s) can be anything of your choosing, but code must be primarily written in Python.
- If you build more than one custom subsystem, each subsystem's code must reside within its own subdirectory within this "monorepo". If building only one sub-system, you can place the code in the project's main directory.
- Each custom subsystem must be a containerized application, each having its own `Dockerfile` with the image hosted on [Docker Hub](https://hub.docker.com/).
- Each custom subsystem must have its own CI/CD pipeline using [GitHub Actions](https://docs.github.com/en/actions), with a separate workflow files for each subsystem. These workflows must be triggered by any code change, whether via `push` or merged `pull request`, to the `main` or `master` branch. The workflows must build, test, deliver the images to Docker Hub, and deploy any subsystems that are designed to run online (i.e. any web apps or other online services) to [Digital Ocean](https://m.do.co/c/4d1066078eb0).
- Each custom subsystem must contain unit tests that provide at least 80% code coverage.
- You are welcome to use computing platforms such as [Raspberry Pi](https://www.raspberrypi.com/) or other embedded or mobile devices you have available, if they make sense for your project.

## Documentation
 
Replace the contents of the [README.md](./README.md) file with a beautifully-formatted Markdown file including:

- a plain-language **description** of your project, including:
- [badges](https://docs.github.com/en/actions/monitoring-and-troubleshooting-workflows/adding-a-workflow-status-badge) at the top of the `README.md` file showing the result of the latest CI/CD of each subsystem.
- links to the container images for each custom subsystem, hosted on [DockerHub](https://hub.docker.com).
- the names of all teammates as links to their GitHub profiles.
- instructions for how to configure and run all parts of your project for any developer on any platform - these instructions must work!
- instructions for how to set up any environment variables and import any starter data into the database, as necessary, for the system to operate correctly when run.
- if there are any "secret" configuration files, such as `.env` or similar files, that are not included in the version control repository, exact instructions for how to create them and what their contents should be must be supplied to the course admins by the due date.
