from PIL import Image, ImageDraw, ImageFont

img = Image.new('RGB', (400, 200), color = (73, 109, 137))
d = ImageDraw.Draw(img)
font = ImageFont.load_default()
d.text((10,60), "Simulation Demo (Upgrade to Run)", fill=(255, 255, 0), font=font)
img.save('assets/sim_demo.png')