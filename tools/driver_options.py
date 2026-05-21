from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# 设置无头模式的 Chrome 选项
options = Options()
options.add_argument("--headless")  # 无头模式
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")  # 防检测

# 启动 Chrome 浏览器
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
