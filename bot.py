import asyncio
import re
import discord
from discord.ext import commands, tasks
from discord.gateway import WebSocketClosure
from discord.utils import get
import copy
import pymysql
import json
import elo
import matching

sqlinfo = open("mysql.json", "r")
sqlcon = json.load(sqlinfo)
condb = None

test = input("test모드 > test입력")
if test == "test":
    condb = "testdb"
else:
    condb = "db"

database = pymysql.connect(
    user=sqlcon["user"],
    host=sqlcon["host"],
    db=sqlcon[condb],
    charset=sqlcon["charset"],
    password=sqlcon["password"],
    autocommit=True,
)

cur = database.cursor()


intent = discord.Intents.all()
bot = commands.Bot(command_prefix="G!", intents=intent)

tokenfile = open("token.txt", "r")
token = tokenfile.read()

isProcess = False
rolecount = 2

vschannel = []
totalscore = [0, 0]
matchingUser = []

card = []

tempscore = [0, 0]
sumcard = [0, 0]
winstrike = [0, 0]
maxws = [0, 0]
turnscore = 0

matchMsg = None

isblind = False


@bot.event
async def on_member_join(member):
    global rolecount
    global vschannel
    global vsguild
    global card
    global matchingUser

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
    global vschannel
    global matchingUser
    global card
    global matchMsg

    matchingUser.clear()

    index = 0
    winindex = 0
    for i in vschannel:
        await i.send(f"제출할 2장의 카드를 입력해주세요. ex)'G!제출 12'\n남은 카드 : {card[index*2+1]}")
        index += 1

        if len(card[index * 2 + 1]) == 0:
            isProcess = False

            vschannel.clear()
            if tempscore[0] > tempscore[1]:
                await bot.get_user(card[0]).send("승리")
                await bot.get_user(card[2]).send("패배")

                winid = card[0]
                loseid = card[2]

                winindex = 0
            elif tempscore[0] < tempscore[1]:
                await bot.get_user(card[0]).send("패배")
                await bot.get_user(card[2]).send("승리")

                winid = card[2]
                loseid = card[0]

                winindex = 1
            else:
                await bot.get_user(card[0]).send("무승부")
                await bot.get_user(card[2]).send("무승부")

                winindex = 2

                winid = card[2]
                loseid = card[0]

            WriteData(winindex, winid, loseid)

            await vsguild.delete()
            matchMsg = None


def WriteData(winindex, winid, loseid):
    global card
    global totalscore
    global cur
    global winstrike
    global maxws

    sql = f"select count(*) from user_{card[0]} where userid={card[2]}"
    cur.execute(sql)
    result = cur.fetchone()[0]

    sql = ""
    sql2 = ""
    sql3 = ""
    sql4 = ""
    winscore = None
    losescore = None
    loseindex = 0

    if winindex == 0:
        loseindex = 1

    elif winindex == 1:
        loseindex = 0

    addstring = ""
    addstring2 = ""

    temp = winstrike[winindex]
    temp += 1

    if temp > maxws[winindex]:
        addstring = f",maxws={temp}"

    sql = f"SELECT winstrike,maxws FROM user_{winid} WHERE userid={loseid}"
    cur.execute(sql)
    result = cur.fetchone()

    if result[0] + 1 > result[1]:
        addstring2 = f",maxws={result[0] + 1}"  # maxws 갱신 string

    strikeBonus = 0
    if not temp == 1:
        while temp > 0:
            strikeBonus += 0.05 * temp
            temp = temp - 1

    if winindex == 2:
        if result == 0:
            sql = f"insert into user_{winid}(userid,draw) values ({loseid},1)"
            sql2 = f"insert into user_{loseid}(userid,draw) values ({winid},1)"
        else:
            sql = (
                f"update user_{loseid} set draw=draw+1,winstrike=0 where userid={winid}"
            )
            sql2 = (
                f"update user_{winid} set draw=draw+1,winstrike=0 where userid={loseid}"
            )
        sql3 = f"update user set draw=draw+1,winstrike=0 where userid={winid}"
        sql4 = f"update user set draw=draw+1,winstrike=0 where userid={loseid}"
    else:
        winscore = elo.rate_1vs1(totalscore[winindex], totalscore[loseindex])[0]
        losescore = elo.rate_1vs1(totalscore[winindex], totalscore[loseindex])[1]

        winscore = totalscore[winindex] + abs(winscore - totalscore[winindex]) * (
            1 + strikeBonus
        )
        if result == 0:
            sql = f"insert into user_{loseid}(userid,lose) values ({winid},1)"
            sql2 = f"insert into user_{winid}(userid,win,winstrike,maxws) values ({loseid},1,1,1)"
        else:
            sql = (
                f"update user_{loseid} set lose=lose+1,winstrike=0 where userid={winid}"
            )
            sql2 = f"update user_{winid} set win=win+1,winstrike=winstrike+1{addstring2} where userid={loseid}"
        sql3 = f"update user set score={winscore}, win=win+1,winstrike=winstrike+1{addstring} where userid={winid}"
        sql4 = f"update user set score={losescore}, lose=lose+1,winstrike=0 where userid={loseid}"

    print(sql)
    print(sql2)
    print(sql3)
    print(sql4)

    cur.execute(sql)
    cur.execute(sql2)
    cur.execute(sql3)
    cur.execute(sql4)


@bot.event
async def on_ready():
    print("ready")
    await bot.change_presence(activity=discord.Game(name="Genius"))


@bot.command()
async def 매칭(ctx, mode=None):
    global card
    global matchingUser
    global rolecount
    global isProcess
    global vschannel
    global vsguild
    global tempscore
    global totalscore
    global matchMsg
    global isblind
    global winstrike
    global maxws

    appinfo = await bot.application_info()

    result = checkuser(ctx)

    if result[0] == 0:
        await ctx.send("가입을 해주세요.")
        return

    if isProcess:
        await ctx.send("이미 하고있는 게임이 있습니다.\n'G!관전'으로 게임을 관전하세요.")
        return

    if ctx.author.id in matchingUser:
        await ctx.send("이미 매칭중입니다.")
        return

    for i in bot.guilds:
        if appinfo.id == i.owner_id:
            await i.delete()

    matchingUser.append(ctx.author.id)

    if matchMsg == None:
        if mode == "blind":
            isblind = True
        else:
            isblind = False
        second = 30
        matchMsg = await ctx.send(
            f"매칭중입니다. {len(matchingUser)}/2\nbline모드 : {isblind}\n{second}초"
        )
        for i in range(6):
            await asyncio.sleep(5)
            if len(matchingUser) == 2:
                return
            second -= 5
            await matchMsg.edit(
                content=f"매칭중입니다. {len(matchingUser)}/2\nbline모드 : {isblind}\n{second}초"
            )
        matchingUser.clear()
        await matchMsg.delete()
        matchMsg = None
    else:
        if len(matchingUser) == 2:
            tempscore = [0, 0]

            rolecount = 2
            print("testteeeeeeeeeeeeee")
            isProcess = True
            await matchMsg.edit(content="대결서버를 만드는 중입니다.")
            vsguild = await bot.create_guild("대결")

            await asyncio.sleep(1)

            await matchMsg.edit(content="채널 권한 조정중입니다.")

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

            await matchMsg.edit(content=invite.url)

            for i in range(len(matchingUser)):
                sql = f"SELECT score,winstrike,maxws FROM user WHERE userid={matchingUser[i]}"
                cur.execute(sql)
                result = cur.fetchone()

                totalscore[i] = result[0]
                winstrike[i] = result[1]
                maxws[i] = result[2]


@bot.command()
async def 관전(ctx):
    global vsguild
    invite = await vsguild.invites()[0]

    await ctx.send(invite.url)


@bot.command()
async def 전적(ctx):
    sql = f"select * from user where userid={ctx.author.id}"
    cur.execute(sql)
    result = cur.fetchone()

    await ctx.send(
        f"{ctx.author.display_name} {result[1]}승 {result[2]}패 {result[3]}무 {result[4]}점"
    )


@bot.command()
async def 제출(ctx, numstr=None):
    global sumcard
    global turnscore
    global isblind
    global tempscore

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
            await ctx.send(f"{num[0]}  {num[1]}")
            sumcard[index // 2] = sum(num)

            await ctx.send(f"당신의 합 : {sumcard[index//2]}")

            if sumcard.count(0) == 0:
                turnscore += 1

                winindex = 0
                loseindex = 0

                if turnscore != 1:
                    return
                if sumcard[0] > sumcard[1]:
                    winindex = 0
                    loseindex = 1

                elif sumcard[0] < sumcard[1]:
                    winindex = 1
                    loseindex = 0

                if winindex == loseindex:
                    for i in vschannel:
                        await i.send("무승부")
                else:
                    tempscore[winindex] += 1

                    if not isblind:
                        await vschannel[loseindex].send("패배")
                        await vschannel[winindex].send("승리")

                        await sendscore()
                    else:
                        if len(card[1]) == 0:
                            await sendscore()

                turnscore = 0
                sumcard = [0, 0]

                await sendinfo()

        except Exception as e:
            print(e)
            print(numstr)
            await ctx.send("잘못입력했습니다.")


@bot.command()
async def 순위(ctx):
    sql = f"select * from user order by score desc"
    cur.execute(sql)
    result = cur.fetchall()
    sendtext = ""

    for i in result:
        sendtext += f"{bot.get_user(i[0]).display_name} {i[1]}승 {i[2]}패 {i[3]}무 {i[4]}점 {i[5]}연승중\n"

    await ctx.send(sendtext)


async def sendscore():
    global vschannel
    global tempscore
    global card

    print("sendscore------------")

    for i in vschannel:
        await i.send(
            f"{bot.get_user(card[0]).display_name} {tempscore[0]} : {tempscore[1]} {bot.get_user(card[2]).display_name}"
        )


def checkuser(ctx):
    sql = f"select count(*) from user where userid={ctx.author.id}"
    cur.execute(sql)

    result = cur.fetchone()

    return result


@bot.command()
async def 가입(ctx):
    result = checkuser(ctx)

    if result[0] == 0:
        sql = f"create table user_{ctx.author.id}(userid bigint not null primary key,win int default 0,lose int default 0,draw int default 0,winstrike int default 0,maxws int default 0)"
        sql2 = f"insert into user(userid) values ({ctx.author.id})"

        cur.execute(sql)
        cur.execute(sql2)
        await ctx.send("가입 완료")
        return
    else:
        await ctx.send("이미 가입되어있습니다.")
        return


bot.run(token)
