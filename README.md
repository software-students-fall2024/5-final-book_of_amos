![Lint-free](https://github.com/nyu-software-engineering/containerized-app-exercise/actions/workflows/lint.yml/badge.svg)
![ML-Client](https://github.com/software-students-fall2024/5-final-book_of_amos/actions/workflows/build-ml-client.yml/badge.svg)
![Web-App](https://github.com/software-students-fall2024/5-final-book_of_amos/actions/workflows/build-web-app.yml/badge.svg)
![DigitialOcean Deployment](https://github.com/software-students-fall2024/5-final-book_of_amos/actions/workflows/deployment.yml/badge.svg)

# New and Improved Rock-Paper Scissors

## Description
Our project is a revamping of our project 4 web-app, complete with new modes and a whole new look!

## Authors
- [Dylan](https://github.com/dm6288)
- [Kevin](https://github.com/naruminato1)
- [Sean](https://github.com/bairixie)
- [Simon](https://github.com/simesherbs)

## Instructions
Simply enter 143.198.0.220 into your browser and play!

### Small note
Due to http secuirty issues, to be able to make use of the gesture recognition mode, you need to whitelist the site in your browser. Go "chrome://flags" and and add the IP to the "Insecure origins treated as secure" whitelist.

## Container Images
- [Web-App](https://hub.docker.com/r/simesherbs/webapp)
- [ML Client](https://hub.docker.com/r/simesherbs/ml_client)
- [MongoDB](https://hub.docker.com/r/simesherbs/db)
- [Nginx](https://hub.docker.com/r/simesherbs/nginx) 

## Local Installation
To install this web-app locally, simply clone the GitHub repo via the command line:
```bash
git clone git@github.com:software-students-fall2024/5-final-book_of_amos.git
```
To build the image for the project simply run the command:
```bash
docker-compose build
```
Then to load the image, simple run:
```bash
docker-compose up
```
Alternatively, you can build and run in the the same command:
```bash
docker-compose up --build
```
Once the image is running, simply visit the web-app at:
http://127.0.0.1:5005/

## Requirements
The only requirement needed to run this project is [Docker](https://www.docker.com/). See install instruction on [their website](https://docs.docker.com/engine/install/).
