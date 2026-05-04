pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        timeout(time: 20, unit: 'MINUTES')
    }

    stages {
        stage('Pull and rebuild') {
            steps {
                sh '''
                    set -eu
                    cd "$DEPLOY_PATH"
                    git fetch --prune origin
                    git pull --ff-only origin main
                    echo "deploying commit: $(git rev-parse --short HEAD)"
                    docker compose build
                    docker compose up -d
                    docker compose ps
                '''
            }
        }
    }
}
