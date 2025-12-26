from PIL import Image
import os

def remove_white_bg(input_path, output_paths):
    print(f"Processing {input_path}...")
    try:
        img = Image.open(input_path).convert("RGBA")
        datas = img.getdata()

        new_data = []
        for item in datas:
            # r, g, b, a = item
            # Logic: If pixel is white, make transparent.
            # If pixel is near white (antialiasing), reduce alpha.
            
            # Simple threshold for pure white background
            # The logo is Green, so Red and Blue components should be significantly lower than 255 if it's foreground.
            # If R, G, B are all high, it's white background.
            
            r, g, b, a = item
            
            # Distance from white
            # Green logo: R and B are low. G is high.
            # White bg: R, G, B are high.
            
            if r > 240 and g > 240 and b > 240:
                new_data.append((255, 255, 255, 0))
            elif r > 200 and g > 200 and b > 200:
                # Semi-transparent edge handling
                # Ramp alpha from 255 (at 200) to 0 (at 240)
                avg = (r + g + b) / 3
                # 200 -> alpha 255
                # 240 -> alpha 0
                alpha_factor = (240 - avg) / 40.0
                if alpha_factor < 0: alpha_factor = 0
                if alpha_factor > 1: alpha_factor = 1
                new_alpha = int(255 * alpha_factor)
                new_data.append((r, g, b, new_alpha))
            else:
                new_data.append(item)

        img.putdata(new_data)
        
        for out in output_paths:
            os.makedirs(os.path.dirname(out), exist_ok=True)
            img.save(out, "PNG")
            print(f"Saved to {out}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inp = r"C:/Users/Saraji/.gemini/antigravity/brain/0f95625b-401d-4d53-b8bc-07a673a8c4e0/form_flow_logo_concept_4_emerald_wave_1766742014609.png"
    outs = [
        r"d:\Form-Flow-AI\form-flow-frontend\public\logo.png",
        r"d:\Form-Flow-AI\form-flow-frontend\public\favicon.png"
    ]
    remove_white_bg(inp, outs)
