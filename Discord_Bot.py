import discord
from discord.ext import commands
import requests
from urllib import parse
import os
from openai import OpenAI
import json
from dotenv import load_dotenv
from pathlib import Path
import asyncio
import yt_dlp

load_dotenv(dotenv_path="./.env")

### Openai ###

client = OpenAI(api_key = os.getenv('openai_key'))

SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "당신은 AI 호선이라는 이름의 디스코드 봇입니다."
        "미국으로 떠나버린 이호선을 대체하기 위해 만들어졌습니다. "
        "이호선은 무릎과 불족발을 치환하는데 성공한 아주대학교의 생명공학도입니다."
        "당신은 디스코드 서버에서 사람들에게 도움을 주는 것이 주 역할이며, "
        "한국의 20대 남자의 전형적인 말투로, 친구에게 말하듯 반말로 편하게 대답합니다."
    )
}

chat_histories = {}

def manage_chat_history(user_id, new_message, max_messages=10):
    if user_id not in chat_histories:
        chat_histories[user_id] = []
    
    chat_histories[user_id].append(new_message)
    
    if len(chat_histories[user_id]) > max_messages:
        chat_histories[user_id] = chat_histories[user_id][-max_messages:]

### League of Legends ###


request_header = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    "Accept-Language": "ko,en-US;q=0.9,en;q=0.8,es;q=0.7",
                    "Accept-Charset": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Origin": "https://developer.riotgames.com",
                    "X-Riot-Token": os.getenv('riot_api_key')
                }

def getNameTag(summonerName):
    splitted_name = summonerName.split('#')
    if len(splitted_name) == 2:
        gameName, tagLine = splitted_name
    else:
        gameName = summonerName
        tagLine = "KR1"

    return gameName, tagLine

def get_PUUID(gameName, tagLine):
    gameName = parse.quote(gameName)
    tagLine = parse.quote(tagLine)
    
    url = "https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{}/{}".format(gameName, tagLine)
    return requests.get(url, headers=request_header).json()

def get_summonerinfo_by_puuid(puuid):
    url = "https://kr.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/"+puuid
    return requests.get(url, headers=request_header).json()


def league_v4_summoner_league(summoner_id):
    url = "https://kr.api.riotgames.com/lol/league/v4/entries/by-summoner/"+summoner_id
    return requests.get(url, headers=request_header).json()

def queueTypeCheck(queueType):
    if queueType=="RANKED_FLEX_SR":
        return "자유랭크"
    elif queueType=="RANKED_SOLO_5x5":
        return "솔로랭크"
    else:
        return queueType

rank_color = {
    'IRON' : 0x413530,
    'BRONZE' : 0x6B463C,
    'SILVER' : 0x8396A0,
    'GOLD' : 0xBB9660,
    'PLATINUM' : 0x5CB9AE,
    'EMERALD' : 0x035B36,
    'DIAMOND' : 0x265BAB,
    'MASTER' : 0xB84EF1,
    'GRANDMASTER' : 0xBA1B1B,
    'CHALLENGER' : 0xD7FAFA 
}

#########################

app = commands.Bot(command_prefix = '$', help_command=None,intents=discord.Intents.all())

@app.event
async def on_ready():
    print(f'Login bot: {app.user}')
    game=discord.Game("대화")
    
    await app.change_presence(status=discord.Status.online, activity=game)

@app.command()
async def help(ctx):
    embed = discord.Embed(title="도움말", color=0x000000)
    embed.add_field(name="$hello", value="AI호선과 인사합니다.", inline=False)
    embed.add_field(name="$chat [질문], $c [질문], $호선아 [질문]", value="AI호선에게 질문합니다.", inline=False)
    embed.add_field(name="$lol [닉네임#태그], $l [닉네임#태그], $롤 [닉네임#태그]", value="롤 티어를 검색합니다.", inline=False)
    embed.add_field(name="$image [설명], $img [설명], $그림 [설명]", value="AI호선에게 그림을 부탁합니다.", inline=False)
    embed.add_field(name="$tts [문장], $speak [문장], $말해 [문장]", value="입력한 문장을 음성 채널에서 읽어줍니다.", inline=False)
    embed.add_field(name="$play [검색어], $p [검색어]", value="유튜브에서 음악을 검색하여 재생합니다. 재생 중이면 대기열에 추가됩니다.", inline=False)
    embed.add_field(name="$queue", value="현재 대기열에 있는 곡들을 확인합니다.", inline=False)
    embed.add_field(name="$skip", value="현재 재생 중인 곡을 스킵하고 다음 곡을 재생합니다.", inline=False)
    embed.add_field(name="$stop", value="재생을 멈추고 대기열을 초기화합니다.", inline=False)
    embed.add_field(name="$enter, $siu", value="현재 사용자가 있는 음성 채널에 봇이 들어가 인사합니다.", inline=False)
    embed.add_field(name="$exit", value="봇이 음성 채널에서 나갑니다.", inline=False)
    
    await ctx.send(embed=embed)
     
@app.command()
async def hello(ctx):
    await ctx.channel.send('안녕하세요? AI 호선입니다. 명령어는 $help 로 확인해주세요.')
    
@app.command(aliases = ['c','호선아'])
async def chat(ctx, *args):
    prompt = ' '.join(args)
    user_id = str(ctx.author.id)
    
    try:
        messages = [SYSTEM_MESSAGE]
        if user_id in chat_histories:
            messages.extend(chat_histories[user_id])
        
        user_message = {"role": "user", "content": prompt}
        messages.append(user_message)
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.75
        )
        
        assistant_message = {
            "role": "assistant",
            "content": response.choices[0].message.content
        }
        
        manage_chat_history(user_id, user_message)
        manage_chat_history(user_id, assistant_message)
        
        await ctx.send(response.choices[0].message.content)
    
    except Exception as e:
        print(f"Chat 함수 오류 발생: {str(e)}")
        await ctx.send("Error (chat)")
    

@app.command(aliases = ['l','롤'])
async def lol(ctx, arg):
    embed=discord.Embed(title="League of Legends 전적검색[KR]", color=0x000000)
    error_occured = False
    
    #### Search Riot Id ####
    try:
        gameName, tagLine = getNameTag(arg)
        puuid = get_PUUID(gameName, tagLine).get('puuid')

        summoner_info = get_summonerinfo_by_puuid(puuid)

        summoner_id = summoner_info.get('id')
        prev_name = summoner_info.get('name')
        summonerLevel = summoner_info.get('summonerLevel')
        profileIconId = summoner_info.get('profileIconId')
    
    except:
        embed.add_field(name = arg, value="소환사 이름이 없습니다. 띄어쓰기 없이 [Name#Tag]와 같이 입력해주세요.", inline=False)
        error_occured = True
    
    ### Error occurred while searching Riot ID.
    if not error_occured:
        #### Load Rank info ####
        try:
            summoner_rank = league_v4_summoner_league(summoner_id)
            tier = summoner_rank[0].get('tier')
            rank = summoner_rank[0].get('rank')
            wins = summoner_rank[0].get('wins')
            losses = summoner_rank[0].get('losses')
            leaguePoints = summoner_rank[0].get('leaguePoints')
            queueType = summoner_rank[0].get('queueType')
            queueType = queueTypeCheck(queueType)
            
            embed.color = rank_color[tier]
            embed.add_field(name="{}#{} (prev.{}) Lv.{}".format(gameName, tagLine, prev_name, summonerLevel),
                    value="{} {} {} {}P\n{}승 {}패".format(queueType, tier, rank, leaguePoints, wins, losses),
                    inline=False)
            
        except:
            embed.add_field(name = "{}#{} (prev.{}) Lv.{}".format(gameName, tagLine, prev_name, summonerLevel), 
                            value="unranked", inline=False)
        
        
        #### Thumbnail Setting ####
        
        icon_url = "https://ddragon.leagueoflegends.com/cdn/10.18.1/img/profileicon/{}.png".format(profileIconId)
        
        try:
            response = requests.get(icon_url)
            response.raise_for_status()
            embed.set_thumbnail(url = icon_url)
        
        except:
            icon_url = "https://ddragon.leagueoflegends.com/cdn/10.18.1/img/profileicon/6.png"
            embed.set_thumbnail(url = icon_url)
        
    
    #### Result ####
    await ctx.send(embed=embed)

@app.command(aliases = ['그림', 'img'])
async def image(ctx, *args):
    prompt = ' '.join(args)
    try:
        await ctx.send("그리는 중.. [요청:{}]".format(prompt))
  
        embed=discord.Embed(title="그림 그려왔다.", description=prompt, color=0x34EBC6)
        
        resp = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        image_url = resp.data[0].url
        embed.set_image(url=image_url)
        
        await ctx.send(embed=embed)
        
    except Exception as err:
        await ctx.send("Error (image)")
        await ctx.send(err)

@app.command(aliases=['speak', '말해'])
async def tts(ctx, *args):
    try:
        text = ' '.join(args)
        if not text:
            await ctx.send("텍스트를 입력해주세요!")
            return

        # 음성 파일 경로 설정
        speech_file_path = Path(__file__).parent / f"speech_{ctx.message.id}.mp3"

        # TTS 생성
        response = client.audio.speech.create(
            model="tts-1",
            voice="fable",  # 다른 목소리 옵션: alloy, echo, fable, onyx, nova, shimmer
            input=text
        )

        # 파일로 저장
        response.write_to_file(speech_file_path)  # stream_to_file 대신 write_to_file 사용

        # 사용자가 음성채널에 있는지 확인
        if ctx.author.voice is None:
            await ctx.send("음성 채널에 먼저 입장해주세요!")
            return

        voice_channel = ctx.author.voice.channel

        # 봇이 이미 음성채널에 연결되어 있는지 확인
        voice_client = discord.utils.get(app.voice_clients, guild=ctx.guild)

        if voice_client is None:
            # 봇이 음성채널에 연결되어 있지 않으므로 연결 시도
            voice_client = await voice_channel.connect()
        else:
            # 봇이 이미 연결되어 있으나 다른 채널에 있을 경우 이동
            if voice_client.channel != voice_channel:
                await voice_client.move_to(voice_channel)

        # 음성 재생
        audio_source = discord.FFmpegPCMAudio(str(speech_file_path))
        if not voice_client.is_playing():
            voice_client.play(audio_source)
            await ctx.send("음성을 재생합니다.")
        else:
            # 현재 재생 중인 음성이 있을 경우 큐에 추가하거나 처리
            await ctx.send("현재 음성이 재생 중입니다. 잠시 후 다시 시도해주세요.")

        #삭제
        # speech_file_path.unlink()

    except Exception as e:
        print(f"TTS 함수 오류 발생: {str(e)}")
        await ctx.send("Error (tts)")
        if 'speech_file_path' in locals() and speech_file_path.exists():
            speech_file_path.unlink()



@app.command(aliases=['siu'])
async def enter(ctx):
    hello_mp3_path = "./musics/hello.mp3"
    hello_source = discord.FFmpegPCMAudio(str(hello_mp3_path))
    
    try:
        # 사용자가 음성채널에 있는지 확인
        if ctx.author.voice is None:
            await ctx.send("음성 채널에 먼저 입장해주세요!")
            return

        voice_channel = ctx.author.voice.channel

        # 봇이 이미 음성채널에 연결되어 있는지 확인
        voice_client = discord.utils.get(app.voice_clients, guild=ctx.guild)

        if voice_client is not None:
            if voice_client.channel == voice_channel:
                await ctx.send("siuuuuuuuuuuuuuu!")
                voice_client.play(hello_source)
            else:
                await voice_client.move_to(voice_channel)
                await ctx.send(f"음성 채널을 {voice_channel.name}(으)로 이동했습니다.")
        else:
            await voice_channel.connect()
            
            # 안녕하세요 음성 송출
            voice_client = discord.utils.get(app.voice_clients, guild=ctx.guild)
            voice_client.play(hello_source)
            
            await ctx.send(f"{voice_channel.name} 채널에 입장했습니다. siuuuuuuuuuuuuuuuu!")

    except Exception as e:
        print(f"Enter 명령어 오류 발생: {str(e)}")
        await ctx.send("Error (enter)")

@app.command(name='exit')
async def exit_voice(ctx):
    try:
        voice_client = discord.utils.get(app.voice_clients, guild=ctx.guild)

        if voice_client is not None:
            await voice_client.disconnect()
            await ctx.send("음성 채널에서 나갔습니다.")
        else:
            await ctx.send("봇이 현재 음성 채널에 연결되어 있지 않습니다.")

    except Exception as e:
        print(f"Exit 명령어 오류 발생: {str(e)}")
        await ctx.send("Error (exit)")


queues = {}

def get_queue(guild_id):
    if guild_id not in queues:
        queues[guild_id] = []
    return queues[guild_id]

def play_next(guild):
    """ 현재 플레이가 끝나면 자동으로 호출되어 다음 곡을 재생하는 함수 """
    voice_client = discord.utils.get(app.voice_clients, guild=guild)
    queue = get_queue(guild.id)

    if queue and voice_client and not voice_client.is_playing():
        title, url = queue.pop(0)
        source = discord.FFmpegPCMAudio(url, options='-vn')
        voice_client.play(source, after=lambda e: play_next(guild))

@app.command(aliases=['p'])
async def play(ctx, *, search: str):
    # 명령어 사용한 유저가 음성 채널에 있는지 확인
    if ctx.author.voice is None:
        await ctx.send("음성 채널에 먼저 들어가줘.")
        return

    voice_channel = ctx.author.voice.channel
    voice_client = discord.utils.get(app.voice_clients, guild=ctx.guild)

    # 봇이 아직 음성 채널에 연결되어 있지 않다면 연결
    if voice_client is None:
        voice_client = await voice_channel.connect()
    else:
        # 다른 채널에 있다면 이동
        if voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)

    # yt_dlp 옵션 설정
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'default_search': 'ytsearch',
        'noplaylist': True,
    }

    # 유튜브에서 검색어로 영상 정보 추출
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search, download=False)
        if 'entries' in info and len(info['entries']) > 0:
            info = info['entries'][0]
        url = info['url']
        title = info.get('title', '제목 없음')

    queue = get_queue(ctx.guild.id)

    # 현재 플레이 중인 곡이 있는지 확인
    if voice_client.is_playing():
        # 곡이 재생 중이면 큐에 추가
        queue.append((title, url))
        await ctx.send(f"대기열: {len(queue)} - {title}")
    else:
        # 현재 재생중이 아니면 바로 재생
        source = discord.FFmpegPCMAudio(url, options='-vn')
        voice_client.play(source, after=lambda e: play_next(ctx.guild))
        await ctx.send(f"지금 재생 중: {title}")

@app.command(name='queue')
async def show_queue(ctx):
    queue = get_queue(ctx.guild.id)
    if not queue:
        await ctx.send("대기열에 노래가 없습니다.")
    else:
        msg = "대기열:\n"
        for i, (title, url) in enumerate(queue, start=1):
            msg += f"{i}. {title}\n"
        await ctx.send(msg)

@app.command()
async def skip(ctx):
    voice_client = discord.utils.get(app.voice_clients, guild=ctx.guild)
    if voice_client is None or not voice_client.is_playing():
        await ctx.send("재생 중인 곡이 없습니다.")
        return
    
    voice_client.stop()  # 현재 곡을 스킵 -> after 콜백으로 다음 곡 재생 시도
    await ctx.send("현재 곡을 스킵했습니다.")

@app.command(name='stop')
async def stop_playing(ctx):
    voice_client = discord.utils.get(app.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_connected():
        # 큐 초기화
        queues[ctx.guild.id] = []
        voice_client.stop()
        await ctx.send("재생을 멈추고 대기열을 비웠습니다.")
    else:
        await ctx.send("음성 채널에 연결해주세요.")

app.run(os.getenv('discord_key'))