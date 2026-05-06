import discord
from discord.ext import commands, tasks
import os
import qrcode
import io
from promptpay import qrcode as pp_qr
import datetime
import json

PROMPTPAY_ID = "0886560336" # แก้เป็นเบอร์ท่าน
ADMIN_CHANNEL_ID = 1500036196703797308 # แก้เป็น ID ห้องแอดมินท่าน
VIP_DAYS = 30

TOKEN = os.getenv('DISCORD_TOKEN')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

pending_orders = {}
DB_FILE = "vip_db.json"

def load_db():
    try:
        with open(DB_FILE, 'r') as f: return json.load(f)
    except: return {}

def save_db(data):
    with open(DB_FILE, 'w') as f: json.dump(data, f, indent=4)

vip_data = load_db()

class VIPShopView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="🥉 Bronze 50฿", style=discord.ButtonStyle.secondary, custom_id="bronze_v2")
    async def bronze_button(self, i: discord.Interaction, b: discord.ui.Button): await self.create_payment(i, "VIP Bronze", 50)
    @discord.ui.button(label="🥈 Silver 150฿", style=discord.ButtonStyle.secondary, custom_id="silver_v2")
    async def silver_button(self, i: discord.Interaction, b: discord.ui.Button): await self.create_payment(i, "VIP Silver", 150)
    @discord.ui.button(label="🥇 Gold 300฿", style=discord.ButtonStyle.secondary, custom_id="gold_v2")
    async def gold_button(self, i: discord.Interaction, b: discord.ui.Button): await self.create_payment(i, "VIP Gold", 300)
    async def create_payment(self, i: discord.Interaction, product_name: str, price: int):
        payload = pp_qr.generate_payload(PROMPTPAY_ID, amount=price)
        img = qrcode.make(payload)
        buffer = io.BytesIO()
        img.save(buffer, 'PNG')
        buffer.seek(0)
        order_id = f"{i.user.id}_{int(datetime.datetime.now().timestamp())}"
        pending_orders[order_id] = {"user_id": i.user.id, "product": product_name, "price": price}
        view = ConfirmPaymentView(order_id)
        file = discord.File(buffer, filename="qr.png")
        embed = discord.Embed(title=f"💸 ชำระเงิน {product_name}", description=f"**ยอดชำระ: {price}฿**\n**อายุ: {VIP_DAYS} วัน**\n\n1. สแกน QR เพื่อจ่ายเงิน\n2. กดปุ่ม `📢 แจ้งโอนเงินแล้ว` ด้านล่าง", color=0x00ff00)
        embed.set_image(url="attachment://qr.png")
        await i.response.send_message(embed=embed, file=file, view=view, ephemeral=True)

class ConfirmPaymentView(discord.ui.View):
    def __init__(self, order_id): super().__init__(timeout=600); self.order_id = order_id
    @discord.ui.button(label="📢 แจ้งโอนเงินแล้ว", style=discord.ButtonStyle.success)
    async def confirm_button(self, i: discord.Interaction, b: discord.ui.Button):
        order = pending_orders.get(self.order_id)
        if not order: return await i.response.send_message("ออเดอร์หมดอายุแล้ว", ephemeral=True)
        admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
        if admin_channel:
            user = i.user
            embed = discord.Embed(title="🔔 ออเดอร์ใหม่รอตรวจ", description=f"**ลูกค้า:** {user.mention} `{user.id}`\n**สินค้า:** {order['product']}\n**ยอด:** {order['price']}฿", color=0xffa500)
            await admin_channel.send(embed=embed, view=ApproveView(self.order_id))
            await i.response.edit_message(content="✅ แจ้งโอนแล้ว รอแอดมินตรวจ 1-5 นาที", embed=None, view=None, attachments=[])

class ApproveView(discord.ui.View):
    def __init__(self, order_id): super().__init__(timeout=None); self.order_id = order_id
    @discord.ui.button(label="✅ อนุมัติ", style=discord.ButtonStyle.success, custom_id="approve_v2")
    async def approve_button(self, i: discord.Interaction, b: discord.ui.Button):
        order = pending_orders.pop(self.order_id, None)
        if not order: return await i.response.send_message("ออเดอร์นี้ถูกจัดการไปแล้ว", ephemeral=True)
        guild = i.guild
        member = guild.get_member(order['user_id'])
        role = discord.utils.get(guild.roles, name=order['product'])
        if member and role:
            await member.add_roles(role)
            user_id_str = str(member.id)
            expire_date = datetime.datetime.now() + datetime.timedelta(days=VIP_DAYS)
            vip_data[user_id_str] = {"role": order['product'], "expire": expire_date.strftime("%Y-%m-%d %H:%M:%S")}
            save_db(vip_data)
            await i.response.edit_message(content=f"✅ อนุมัติ {order['product']} ให้ {member.mention} เรียบร้อย", embed=None, view=None)
            try: await member.send(f"🎉 ยินดีด้วย! คุณได้รับยศ {order['product']} แล้ว\n**หมดอายุ:** {expire_date.strftime('%d/%m/%Y')}")
            except: pass

@tasks.loop(hours=24)
async def check_vip_expiry():
    await bot.wait_until_ready()
    now = datetime.datetime.now()
    users_to_remove = []
    for user_id, data in vip_data.items():
        expire_date = datetime.datetime.strptime(data["expire"], "%Y-%m-%d %H:%M:%S")
        if now >= expire_date:
            users_to_remove.append(user_id)
            for guild in bot.guilds:
                member = guild.get_member(int(user_id)); role = discord.utils.get(guild.roles, name=data["role"])
                if member and role:
                    await member.remove_roles(role)
                    try: await member.send(f"😢 ยศ {data['role']} ของคุณหมดอายุแล้ว\nพิมพ์ `!เมนู` เพื่อต่ออายุ")
                    except: pass
    for user_id in users_to_remove: del vip_data[user_id]
    if users_to_remove: save_db(vip_data)

@bot.event
async def on_ready():
    print(f'บอท {bot.user} ออนไลน์แล้ว!')
    bot.add_view(VIPShopView())
    if not check_vip_expiry.is_running(): check_vip_expiry.start()

@bot.command(name="เมนู")
@commands.has_permissions(administrator=True)
async def menu_th(ctx):
    embed = discord.Embed(title="👑 PREMIUM MEMBERSHIP", description=f"**แพ็กเกจ {VIP_DAYS} วัน**\n\n**🥉 BRONZE** `50฿`\n`└ EXP x1.5 | ห้องพิเศษ`\n\n**🥈 SILVER** `150฿`\n`└ EXP x2.0 | ห้องพิเศษ | สีชื่อ`\n\n**🥇 GOLD** `300฿`\n`└ EXP x3.0 | ห้องพิเศษ | สีชื่อ | ยศทอง`", color=0x2b2d31)
    await ctx.send(embed=embed, view=VIPShopView())

@bot.command(name="เช็คยศ")
async def check_vip(ctx):
    user_id_str = str(ctx.author.id)
    if user_id_str in vip_data:
        d = vip_data[user_id_str]
        await ctx.send(f"✅ คุณมียศ {d['role']}\n**หมดอายุ:** {d['expire']}", ephemeral=True)
    else: await ctx.send("❌ คุณยังไม่มียศ VIP พิมพ์ `!เมนู` เพื่อซื้อเลย", ephemeral=True)

bot.run(TOKEN)