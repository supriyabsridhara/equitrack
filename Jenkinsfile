pipeline {
    agent any

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '15'))
    }

    // Use a GitHub webhook when Jenkins is reachable; otherwise this polls every ~5 minutes.
    triggers { pollSCM('H/5 * * * *') }

    environment {
        IMAGE_NAME = 'equitrack'
        IMAGE_TAG  = "${env.BUILD_NUMBER}"
        VENV       = "${env.WORKSPACE}/.venv"
    }

    stages {
        stage('Checkout') {
            steps { checkout scm }
        }

        stage('Install dependencies') {
            steps {
                sh '''
                    python3 -m venv "$VENV"
                    . "$VENV/bin/activate"
                    pip install --upgrade pip
                    pip install -r requirements.txt
                '''
            }
        }
        stage('Install dependencies') {
            steps {
                sh '''
                    python3.12 -m venv "$VENV"
                    . "$VENV/bin/activate"
                    pip install --upgrade pip
                    pip install -r requirements.txt
                '''
             }
        }
        
        stage('Lint') {
            steps { sh '. "$VENV/bin/activate" && flake8 app tests dev' }
        }

        stage('Test') {
            steps {
                sh '. "$VENV/bin/activate" && python -m pytest tests/ -v --junitxml=reports/junit.xml'
            }
            post { always { junit allowEmptyResults: true, testResults: 'reports/junit.xml' } }
        }

        stage('Build Docker image') {
            steps { sh 'docker build -t ${IMAGE_NAME}:${IMAGE_TAG} -t ${IMAGE_NAME}:latest .' }
        }

        stage('Deploy to Kubernetes') {
            when {
                expression { env.BRANCH_NAME == 'main' || env.GIT_BRANCH in ['origin/main', 'main'] }
            }
            steps {
                // Secret is created from a Jenkins credential, so the API key never touches Git or the image.
                withCredentials([string(credentialsId: 'alpha-vantage-key', variable: 'AV_KEY')]) {
                    sh '''
                        kubectl create secret generic equitrack-secrets \
                          --from-literal=ALPHA_VANTAGE_API_KEY="$AV_KEY" \
                          --from-literal=MONGODB_URI="mongodb://mongo:27017/equitrack" \
                          --dry-run=client -o yaml | kubectl apply -f -
                    '''
                }
                sh '''
                    minikube image load ${IMAGE_NAME}:${IMAGE_TAG}
                    kubectl apply -f k8s/
                    kubectl set image deployment/equitrack-app app=${IMAGE_NAME}:${IMAGE_TAG}
                    kubectl rollout status deployment/equitrack-app --timeout=180s
                    kubectl get pods,svc
                '''
            }
        }
    }

    post {
        success { echo "Built and verified ${env.IMAGE_NAME}:${env.IMAGE_TAG}" }
        failure { echo 'Pipeline failed. Check the stage logs above (tests, lint, Docker or kubectl).' }
    }
}
