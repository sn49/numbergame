import asyncio
import re
import discord
from discord.ext import commands, tasks
from discord.utils import get
import copy

intent = discord.Intents.all()
bot = commands.Bot(command_prefix="G!", intents=intent)

tokenfile = open("token.txt", "r")
token = tokenfile.read()

isProcess = False
rolecount = 2


@bot.event
async def on_member_join(member):
    global rolecount
    global vschannel
    global vsguild
    global card

    if member.id in card:
        index = card.index(member.id)
        prole = discord.utils.get(member.guild.roles, name=f"P{index//2+1}")
        await member.add_roles(prole)
        rolecount -= 1

        if rolecount == 0:
            await sendinfo()


async def sendinfo():
    global vsguild
    global isProcess
    index = 0
    for i in vschannel:
        await i.send(f"제출할 2장의 카드를 입력해주세요. ex)'G!제출 12'\n남은 카드 : {card[index*2+1]}")
        index += 1

        if len(card[index * 2 + 1]) == 0:
            isProcess = False
            await vsguild.delete()
            vsguild = None
            vschannel.clear()
            if tempscore[0] > tempscore[1]:
                await bot.get_user(card[0]).send("승리")
                await bot.get_user(card[1]).send("패배")
            elif tempscore[0] < tempscore[1]:
                await bot.get_user(card[0]).send("패배")
                await bot.get_user(card[1]).send("승리")
            else:
                await bot.get_user(card[0]).send("무승부")
                await bot.get_user(card[1]).send("무승부")


@bot.event
async def on_ready():
    print("ready")
    await bot.change_presence(activity=discord.Game(name="Genius"))


matchingUser = []

card = []
vschannel = []
tempscore = [0, 0]


@bot.command()
async def 매칭(ctx):
    global card
    global matchingUser
    global rolecount
    global isProcess
    global vschannel
    global vsguild
    global tempscore

    appinfo = await bot.application_info()

    if isProcess:
        await ctx.send("이미 하고있는 게임이 있습니다.")
        return

    if ctx.author.id in matchingUser:
        await ctx.send("이미 매칭중입니다.")
        return

    for i in bot.guilds:
        if appinfo.id == i.owner_id:
            await i.delete()

    matchingUser.append(ctx.author.id)

    if len(matchingUser) == 2:
        tempscore = [0, 0]

        rolecount = 2
        print("testteeeeeeeeeeeeee")
        isProcess = True
        pmsg = await ctx.send(content="대결서버를 만드는 중입니다.")
        vsguild = await bot.create_guild("대결")

        await asyncio.sleep(1)

        await pmsg.edit(content="채널 권한 조정중입니다.")

        perms = discord.Permissions(read_messages=False)
        role1 = await vsguild.create_role(name="P1", permissions=perms)
        role2 = await vsguild.create_role(name="P2", permissions=perms)

        channels = await vsguild.fetch_channels()

        for g in channels:
            print(g.name)
            if g.name == "general":
                try:
                    await g.set_permissions(role1, read_messages=False)
                    await g.set_permissions(role2, read_messages=False)
                except:
                    pass

        vschannel.append(await vsguild.create_text_channel("채널1"))
        await vschannel[0].set_permissions(
            vsguild.default_role, send_messages=False, read_messages=True
        )
        await vschannel[0].set_permissions(role2, read_messages=False)
        await vschannel[0].set_permissions(role1, send_messages=True)

        vschannel.append(await vsguild.create_text_channel("채널2"))
        await vschannel[1].set_permissions(
            vsguild.default_role, send_messages=False, read_messages=True
        )
        await vschannel[1].set_permissions(role1, read_messages=False)
        await vschannel[1].set_permissions(role2, send_messages=True)

        invite = await vschannel[0].create_invite()

        temp = copy.deepcopy(matchingUser)
        card = [
            temp[0],
            [1, 1, 1, 2, 2, 2, 3, 3, 3, 4],
            temp[1],
            [1, 1, 1, 2, 2, 2, 3, 3, 3, 4],
        ]
        matchingUser.clear()

        await pmsg.edit(content=invite.url)


sumcard = [0, 0]


@bot.command()
async def 제출(ctx, numstr=None):
    global sumcard
    if ctx.author.id in card:
        if numstr == None:
            await ctx.send("제출할 숫자를 적지 못했습니다.")
            return

        if len(numstr) != 2:
            await ctx.send("제출할 숫자 2개를 적어주세요.")
            return

        if not re.match(r"\d{2}", numstr):
            await ctx.send("다시 입력해주세요.")
            return
        index = card.index(ctx.author.id)

        if sumcard[index // 2] != 0:
            await ctx.send("이미 제출했습니다.")
            return

        try:
            numstr = int(numstr)

            num = [numstr // 10, numstr % 10]

            await ctx.send(f"{num[0]}  {num[1]}")
            sumcard[index // 2] = sum(num)

            if num[0] == num[1]:
                if card[index + 1].count(num[0]) >= 2:

                    card[index + 1].remove(num[0])
                    card[index + 1].remove(num[0])
                else:
                    raise Exception()
            else:
                if (
                    card[index + 1].count(num[0]) >= 1
                    and card[index + 1].count(num[1]) >= 1
                ):
                    card[index + 1].remove(num[0])
                    card[index + 1].remove(num[1])
                else:
                    raise Exception()

            await ctx.send(f"당신의 합 : {sumcard[index//2]}")

            if sumcard.count(0) == 0:
                if sumcard[0] > sumcard[1]:
                    await vschannel[0].send("승리")
                    await vschannel[1].send("패배")
                    tempscore[0] += 1
                elif sumcard[0] < sumcard[1]:
                    await vschannel[0].send("패배")
                    await vschannel[1].send("승리")
                    tempscore[1] += 1

                else:
                    for i in vschannel:
                        await i.send("무승부")
                sumcard = [0, 0]
                for i in vschannel:
                    await i.send(
                        f"{bot.get_user(card[0]).display_name} {tempscore[0]} : {tempscore[1]} {bot.get_user(card[2]).display_name}"
                    )
                await sendinfo()

        except:
            print(numstr)
            await ctx.send("잘못입력했습니다.")


bot.run(token)
