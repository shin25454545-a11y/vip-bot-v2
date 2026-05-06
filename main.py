import discord
from discord.ext import commands
import datetime
import os
import requests

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# ==================== ตั้งค่าของท่าน ====================
ADMIN_CHANNEL_ID = 150003619703797308 # ไอดีห้องที่ให้บอทแท็กแอดมิน
ADMIN_ROLE_ID = 1250051906076934154 # << แก้ตรงนี้ ใส่ไอดี Role แอดมิน
PROMPTPAY_QR_LINK = "https://promptpay.io/0886560336.png" # QR หลักของท่าน
SLIPOK_API_KEY = os.getenv("SLIPOK_KEY") # ตั้งใน Render ถ้าจะใช้เช็คสลิปออโต้

PACKAGES = {
    "BRONZE": {"price": 50, "days": 30, "role_id": 1499228752223492566},
    "SILVER": {"price": 150, "days": 30, "role_id": 1499228616335714073},
    "GOLD": {"price": 300, "days": 30, "role_id": 1499228473095536977},
    "DIAMOND": {"price": 500, "days": 90, "role_id": 1499228057529406096}
}
# =======================================================

class AdminConfirm(discord.ui.View):
    def __init__(self, user_id, package_name):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.package_name = package_name

    @discord.ui.button(label="อนุมัติ", style=discord.ButtonStyle.green, emoji="✅")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.user_id)
        if not member:
            await interaction.response.send_message("หาสมาชิกไม่เจอ", ephemeral=True)
            return

        package = PACKAGES[self.package_name]
        role = interaction.guild.get_role(package["role_id"])
        await member.add_roles(role)

        expire_date = datetime.datetime.now() + datetime.timedelta(days=package["days"])
        try:
            await member.send(f"🎉 แอดมินอนุมัติแล้ว! คุณได้รับยศ VIP {self.package_name}\nหมดอายุ: {expire_date.strftime('%d/%m/%Y')}")
        except:
            pass # กัน error ถ้าลูกค้าปิด DM

        await interaction.response.edit_message(content=f"✅ อนุมัติให้ {member.mention} เรียบร้อย | หมดอายุ {expire_date.strftime('%d/%m/%Y')}", embed=None, view=None)

    @discord.ui.button(label="ปฏิเสธ", style=discord.ButtonStyle.red, emoji="❌")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.user_id)
        await interaction.response.edit_message(content=f"❌ ปฏิเสธคำขอของ {member.mention} แล้ว", embed=None, view=None)

class ConfirmPayment(discord.ui.View):
    def __init__(self, package_name, price, days):
        super().__init__(timeout=300)
        self.package_name = package_name
        self.price = price
        self.days = days

    @discord.ui.button(label="แจ้งโอนเงินแล้ว + แนบสลิป", style=discord.ButtonStyle.green, emoji="📎")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"1. สแกน QR จ่าย **{self.price}฿**\n2. ส่งรูปสลิปมาในแชทนี้ได้เลย", ephemeral=True)

        def check(m):
            return m.author == interaction.user and m.attachments and m.channel == interaction.channel
        try:
            msg = await bot.wait_for('message', check=check, timeout=300.0)
            slip_url = msg.attachments[0].url

            # ถ้าตั้ง SlipOK ไว้ ให้เช็คออโต้
            if SLIPOK_API_KEY:
                await interaction.followup.send("⏳ กำลังตรวจสอบสลิป...", ephemeral=True)
                r = requests.post("https://api.slipok.com/api/line/apikey/9999", json={
                    "url": slip_url,
                    "apiKey": SLIPOK_API_KEY,
                    "amount": self.price,
                    "log": True
                })
                data = r.json()
                if data.get("success") and data["data"]["amount"] == self.price:
                    await self.give_role(interaction)
                    await msg.delete()
                    return
                else:
                    await interaction.followup.send(f"❌ สลิปไม่ถูกต้อง: {data.get('message', 'ยอดเงินไม่ตรงหรือสลิปซ้ำ')}", ephemeral=True)
                    return

            # ถ้าไม่ใช้ SlipOK ส่งให้แอดมินกด
            admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
            embed = discord.Embed(title="📥 มีคนแจ้งโอน VIP", color=0xffa500)
            embed.add_field(name="ลูกค้า", value=interaction.user.mention)
            embed.add_field(name="แพ็กเกจ", value=f"{self.package_name} {self.price}฿")
            embed.add_field(name="อายุ", value=f"{self.days} วัน")
            embed.set_image(url=slip_url)
            embed.timestamp = datetime.datetime.now()
            await admin_channel.send(f"<@&{ADMIN_ROLE_ID}>", embed=embed, view=AdminConfirm(interaction.user.id, self.package_name))
            await interaction.followup.send("✅ แจ้งแอดมินแล้ว รออนุมัติ 1-5 นาทีนะ", ephemeral=True)

        except:
            await interaction.followup.send("⌛ หมดเวลาส่งสลิป กด `!เมนู` ใหม่นะ", ephemeral=True)

    async def give_role(self, interaction):
        package = PACKAGES[self.package_name]
        role = interaction.guild.get_role(package["role_id"])
        await interaction.user.add_roles(role)
        expire_date = datetime.datetime.now() + datetime.timedelta(days=package["days"])
        # TODO: บันทึกวันหมดอายุลง Database ถ้าต้องการต่ออายุอัตโนมัติ
        await interaction.user.send(f"🎉 ยินดีด้วย! คุณได้รับยศ VIP {self.package_name} แล้ว\nหมดอายุ: {expire_date.strftime('%d/%m/%Y')}")
        await interaction.followup.send("✅ ชำระเงินสำเร็จ รับยศเรียบร้อย! เช็คที่โปรไฟล์ได้เลย", ephemeral=True)

class VIPMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="BRONZE 50฿", style=discord.ButtonStyle.secondary, emoji="🥉", row=0)
    async def bronze(self, i, b): await self.send_payment_menu(i, "BRONZE")
    @discord.ui.button(label="SILVER 150฿", style=discord.ButtonStyle.secondary, emoji="🥈", row=0)
    async def silver(self, i, b): await self.send_payment_menu(i, "SILVER")
    @discord.ui.button(label="GOLD 300฿", style=discord.ButtonStyle.secondary, emoji="🥇", row=0)
    async def gold(self, i, b): await self.send_payment_menu(i, "GOLD")
    @discord.ui.button(label="DIAMOND 500฿", style=discord.ButtonStyle.primary, emoji="💎", row=1)
    async def diamond(self, i, b): await self.send_payment_menu(i, "DIAMOND")

    async def send_payment_menu(self, interaction, package_name):
        package = PACKAGES[package_name]
        embed = discord.Embed(title=f"💎 ชำระเงิน VIP {package_name}", color=0x00FFFF)
        embed.description = f"**ขั้นตอน:**\n1. สแกน QR ด้านล่าง\n2. **กรอกจำนวนเงิน {package['price']}฿ ในแอพธนาคาร**\n3. กดปุ่ม `แจ้งโอนเงินแล้ว + แนบสลิป` ด้านล่าง"
        embed.add_field(name="ยอดชำระ", value=f"{package['price']}฿", inline=True)
        embed.add_field(name="อายุ", value=f"{package['days']} วัน", inline=True)
        embed.set_image(url=PROMPTPAY_QR_LINK)
        embed.set_footer(text="บอทจะตรวจสอบยอดเงินให้ตรงกับแพ็กเกจ")
        await interaction.response.send_message(embed=embed, view=ConfirmPayment(package_name, package['price'], package['days']), ephemeral=True)

@bot.command()
async def เมนู(ctx):
    embed = discord.Embed(title="🏪 ร้าน VIP", description="เลือกแพ็กเกจที่ต้องการได้เลย\nจ่ายผ่าน QR พร้อมเพย์ รับยศทันที", color=0xFFD700)
    await ctx.send(embed=embed, view=VIPMenu())

@bot.command()
async def ต่ออายุ(ctx):
    embed = discord.Embed(title="🔄 ต่ออายุ VIP", description="เลือกแพ็กที่ต้องการต่ออายุ\nระบบจะ + วันเพิ่มให้อัตโนมัติ", color=0x00FF00)
    await ctx.send(embed=embed, view=VIPMenu())

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    bot.add_view(VIPMenu()) # ทำให้ปุ่มใช้ได้ตลอด

bot.run(os.getenv("DISCORD_TOKEN"))
