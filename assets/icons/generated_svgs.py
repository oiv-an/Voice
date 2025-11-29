def get_svg_string(color: str = "red") -> str:
    return f'''<svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
       <circle cx="12" cy="12" r="10" fill="{color}" />
       <path d="M8 8 L16 16 M16 8 L8 16" stroke="white" stroke-width="2" />
    </svg>'''


# Готовые SVG-строки для разных состояний

MIC_IDLE_SVG = get_svg_string(color="#4CAF50")      # зелёный круг — idle/готов
MIC_RECORDING_SVG = get_svg_string(color="#F44336") # красный круг — запись
MIC_PROCESSING_SVG = get_svg_string(color="#FF9800")# оранжевый круг — обработка
APP_ICON_SVG = get_svg_string(color="#2196F3")      # синий круг — иконка приложения