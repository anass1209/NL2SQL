# 🚀 Newsletter Monitor: AI-Powered Personalized News Aggregation

## 📝 Project Overview
Newsletter Monitor is an intelligent, automated newsletter generation platform that I have developed, leveraging cutting-edge AI technologies to deliver personalized, up-to-date information directly to your inbox. By combining advanced search capabilities with AI-powered content summarization, this application transforms how users consume and stay informed about their areas of interest.

## 🌟 Live Demo
🔗 **Deployed Application**: [Newsletter Monitor on Heroku](https://newsletter-app-2f16500b8d45.herokuapp.com/)

## 🌟 Key Features
- **AI-Powered Research**: Utilizes Tavily's advanced search API to gather the most recent and relevant information
- **Intelligent Summarization**: Employs Google Gemini AI to create coherent, well-structured newsletter content
- **Customizable Topics**: Generate newsletters on any subject of interest
- **HTML-Formatted Emails**: Professionally designed, responsive email templates
- **Secure API Integration**: Safe handling of API credentials
- **Real-Time Content Generation**: Instant newsletter creation and delivery

## 🛠 Technologies & Tools
### Backend
- **Language**: Python 3.12
- **Web Framework**: Flask
- **AI Integration**:
  - Tavily Search API
  - Google Gemini AI
- **Email Handling**: SMTP
- **Deployment**: Heroku, Gunicorn

### Frontend
- **Template Engine**: Jinja2
- **Styling**: Bootstrap 5
- **Icons**: Font Awesome

### Dependency Management
- **Options**:
  - pip (requirements.txt)
  - Poetry (pyproject.toml)

### Key Libraries
- LangGraph
- google-generativeai
- tavily-python
- Flask-WTF

## 🔧 Technical Architecture
The application follows a modular, event-driven architecture:
1. **Data Retrieval**: Tavily API searches the web for recent information
2. **Content Processing**: Gemini AI summarizes and structures the content
3. **Email Generation**: Creates a responsive HTML newsletter
4. **Delivery**: Sends personalized newsletter via SMTP

## 🚀 Getting Started

### Prerequisites
- Python 3.12
- Tavily API Key
- Google Gemini API Key
- SMTP-enabled email account

### Installation Methods

#### Option 1: Using pip
1. Clone the repository
```bash
git clone https://github.com/anass1209/newsletter-app.git
cd newsletter-monitor
```

2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

#### Option 2: Using Poetry
1. Clone the repository
```bash
git clone https://github.com/anass1209/newsletter-app.git
cd newsletter-monitor
```

2. Install Poetry (if not already installed)
```bash
pip install poetry
```

3. Install dependencies
```bash
poetry install
```

4. Configure environment variables
- Create a `.env` file
- Add Tavily, Gemini, and email configuration details

5. Run the application
```bash
# Using pip
flask run

# Using Poetry
poetry run flask run
```

## 🔒 Security Features
- API key encryption
- Secure environment variable management
- SMTP connection with TLS
- Input validation

## 🌐 Deployment
- Deployed on Heroku
- Gunicorn configuration included
- Environment-specific settings support

## 📊 Performance & Scalability
- Efficient API usage with caching mechanisms
- Modular design allows easy feature expansion
- Asynchronous processing for quick newsletter generation

## 🤝 Contributing
Contributions are welcome! Please check the issues page or submit a pull request.

## 📄 License
MIT License

## 🏆 Skills Demonstrated
- Full-stack web development
- AI integration
- API consumption
- Email automation
- Security best practices
- Modern Python development
- Cloud deployment (Heroku)
- Containerization and environment management

## 🔍 Keywords
AI Newsletter Generator, Python Web Application, Machine Learning, Natural Language Processing, API Integration, Full-Stack Development, AI-Powered Content Aggregation, Automated Newsletters, Google Gemini, Tavily Search API, Heroku Deployment, Flask, Poetry

---

## 🌟 Star the Repository!
If you find this project interesting, please consider giving it a star ⭐ on GitHub!
