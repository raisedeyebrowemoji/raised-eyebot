import discord
from discord.ext import commands, tasks
import datetime
import random
import asyncio
import json
import math
from Utils import fttt
import requests
import typing_extensions as typing
import time

######################################## BOT SETUP ########################################
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=commands.when_mentioned_or('+', '!!'), intents=intents, help_command=None)


def write_to_log(message):
    dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"-  [{dt}] {message}"
    with open("Data/log.txt", "a") as f:
        f.write(log_msg + "\n")

def command_to_log(user, command, message):
    log_msg = f"{user} used {command} (message: {message})"
    write_to_log(log_msg)

def json_loady(filename, dynamic=False):
    path = f'Data/Dynamic/{filename}.json' if dynamic else f'Data/Static/{filename}.json'
    with open(path, 'r', encoding="utf-8") as f:
        return json.load(f)

def json_dumpy(filename, data):
    with open(f'Data/Dynamic/{filename}.json', 'w') as f:
        json.dump(data, f, indent=4)

TOKENS = json_loady("tokens", False)

def contains_any_substring(target: str, substrings: list) -> bool:
    return any(s in target for s in substrings)

def get_tenor_gif_url(tenor_url: str) -> str:
    # Extract the GIF ID from the URL
    gif_id = tenor_url.split("-")[-1]

    # Fetch GIF data from the Tenor API
    api_url = f"https://tenor.googleapis.com/v2/posts?ids={gif_id}&key={TOKENS['tenor']}"
    response = requests.get(api_url)

    if response.status_code == 200:
        data = response.json()
        try:
            gif_url = data["results"][0]["media_formats"]["gif"]["url"]
            return gif_url
        except (KeyError, IndexError) as e:
            raise Exception(f"Unexpected API response structure: {e}")
    else:
        raise Exception(f"Failed to fetch GIF data: {response.status_code}")

def get_media_links(message: discord.Message) -> list:
    media_links = []

    for attachment in message.attachments:
        content_type = attachment.content_type
        if not (content_type.startswith("image") or content_type.startswith("video")):
            continue
        media_links.append(attachment.url)
    
    for embed in message.embeds:
        url = embed.url
        if not url:
            continue

        if "tenor.com" in url:
            media_links.append(get_tenor_gif_url(url))
            continue

        media_links.append(embed.url)


def handle_high_score(score, user_id, game):
    high_scores = json_loady("high_scores", True)

    if user_id not in high_scores["pong"] or score > high_scores[game][user_id]:
        high_scores[game][user_id] = score
        json_dumpy("high_scores", high_scores)
        return True, high_scores[game][user_id]
    
    return False, high_scores[game][user_id]


################################################# EVENTS ##########################################

@bot.event
async def on_ready():
    print(f'{bot.user} is gah damn ready!!')
    write_to_log("Bot started")
    status = json_loady("misc", True)["status"]
    await bot.change_presence(activity=discord.Game(name=status))
    

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)

    await check_streak(message)

@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    server = bot.get_guild(payload.guild_id)
    channel = server.get_channel_or_thread(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    await handle_reactionboard(message)


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    if isinstance(error, commands.CommandNotFound):
        return
    embed = discord.Embed(
        title="❌ Oopsy whoopsy ain't that a darn shame",
        description=f"An error happened ({error})",
        color=int("FF0000", 16)
    )
    await ctx.send(embed=embed)

######################################## PING (and pong) ########################################

ping_pong_streaks = {}

@bot.command(name="ping", aliases=['p']) 
async def ping(ctx: commands.Context):
    command_to_log(ctx.author, "ping", ctx.message.content)

    await ctx.send(f'Pong!! \n*latency: {bot.latency*1000:.2f}ms*')


    string_id= str(ctx.author.id)
    if string_id not in ping_pong_streaks:
        ping_pong_streaks[string_id] = 0
    else:
        ping_pong_streaks[string_id] += 1
    
    if string_id in ping_pong_streaks and ping_pong_streaks[string_id] > 0:
        emoji = match_emoji(ping_pong_streaks[string_id])

        await ctx.send(emoji + " Streak: " + str(ping_pong_streaks[string_id]))

def match_emoji(score):
        emojis = ['🏓', '🔥', '🔥🔥', '🌋', '🤯', '💣', '😰']
        emoji = emojis[min(math.floor(score/5), len(emojis) - 1)]
        if score >= 30:
            emoji = "😰"*math.floor((score/5)-6)
        return emoji


async def check_streak(message: discord.Message):

    stripped_message = message.content.removeprefix("+").removeprefix("!!").removeprefix("<@1197814253692915774> ")
    id_string = str(message.author.id)


    streak_lost = id_string in ping_pong_streaks and ping_pong_streaks[id_string] > 0 and not(stripped_message.lower().startswith("ping"))
    if not streak_lost:
        return
    
    current_streak = ping_pong_streaks[id_string]

    high_score, is_high_score = handle_high_score(current_streak, id_string, "pong")

    streak_emoji = match_emoji(current_streak)
    high_score_emoji = match_emoji(high_score)

    streak_message = (
        f"🎾 Ping pong streak ended. Score: {streak_emoji} {str(current_streak)}\n"
        f"High score: {high_score_emoji} {str(high_score)}"
    )
    if is_high_score:
        streak_message += "\n**New high score!**"
    
    await message.reply(streak_message)
    del ping_pong_streaks[id_string]

    #write_to_log(f"{message.author} lost their streak of {current_streak} with message: {streak_message}")


######################################## HELP COMMAND ########################################

@bot.command(name="help", aliases=['h'])
async def help(ctx: commands.Context, command: str = None):
    command_to_log(ctx.author, "help", ctx.message.content)

    help_data = json_loady('help', False)

    if command:
        await command_help(ctx, command)
        return
    
    command_list ='- ' + '\n- '.join(help_data.keys())
    help_embed = discord.Embed(
        title="Help", 
        description=f"### Prefixes: +, !!, <@1197814253692915774>. \nList of commands available: \n{command_list}",
        color=discord.Color.yellow()
        )
    
    help_embed.set_footer(text="+help <command> for more info")
    await ctx.send(embed=help_embed)

async def command_help(ctx: commands.Context, command: str):
    help_data = json_loady('help', False)
    command = command.lower()

    if command not in help_data:
        await ctx.send(f"Command {command} not found.")
        return
    command_help = help_data[command]
    main_text = f'''
    **{command_help['short_description']}** \n
    {command_help['long_description']} \n
    Names: "{'", "'.join(command_help['names'])}" \n
    Usage: {ctx.prefix}`{command_help['usage']}`
    '''

    help_embed = discord.Embed(
        title=command.capitalize() + ' help',
        description=main_text,
        color=int(help_data[command]['color'], base=16)
    )
    help_embed.set_footer(text=f"+help for command list")
    await ctx.send(embed=help_embed)



######################################## DICE ROLLING ########################################

@bot.command(name="rolldice", aliases=['roll', 'dice', 'd'])
async def rolldice(ctx: commands.Context, faces):
    command_to_log(ctx.author, "rolldice", ctx.message.content)
    try:
        faces = float(faces)
        if faces < 1:
            await ctx.send("dice too small 💔")
            return

        if faces == 2:
            await coin_flip(ctx)
            return

        await dice_roll(ctx, faces)
    except Exception as e:
        await ctx.send("Sorry, don't have that dice yet. Gotta stock up....,")

async def coin_flip(ctx: commands.Context):
    await ctx.send("Flipping my limited edition Eyebot™ coin...")
    await asyncio.sleep(2)

    if random.randint(1, 100) == 1:
        await ctx.reply("Flipped a... rim?!?!?!? ???!?!")
        await ctx.send("holy crap")
        return "rim"

    outcome = random.choice(["heads", "tails"])
    await ctx.reply(f"Flipped a {outcome}!")
    return outcome


async def dice_roll(ctx: commands.Context, faces):
    integer = round(faces) == faces

    if integer:
        faces = int(faces)
        await ctx.send(f"Rolling my limited edition Eyebot™ d-{faces}...")
    else:
        await ctx.send(f"Rolling my limited edition quantum Eyebot™ d-{faces}...")
    
    await asyncio.sleep(2)
    if integer:
        outcome = random.randint(1, faces)
    else:
        outcome = random.uniform(1, faces)
    await ctx.reply(f"Rolled a {outcome}!")
    if faces == 1:
        await ctx.send("what a surprise")
    return outcome


@bot.command(name="coinflip", aliases=['coin', 'flip', 'cf'])  
async def coinflip(ctx: commands.Context):  
    command_to_log(ctx.author, "coinflip", ctx.message.content)

    await coin_flip(ctx)

####################################### REACTIONBOARD #########################################


async def handle_reactionboard(message: discord.Message):
    # define
    rb_setups = json_loady("reactionboard_setups", True)
    rb_messages = json_loady("reactionboard_messages", True)
    server_id = str(message.guild.id)
    message_id = str(message.id)


    # guard
    if not server_id in rb_setups:
        return
    
    rb_setup = rb_setups[server_id]

    if message.channel.id == rb_setup["channel"]:
        return
    
    if server_id not in rb_messages:
        rb_messages[server_id] = {}

    is_already_in_reactionboard = message_id in rb_messages[server_id] # no more spaghety :(

    reactionboard_reactions = []
    for msg_reaction in message.reactions:
        if msg_reaction.count < rb_setup["threshold"]:
            continue

        reactionboard_reactions.append({
            'emoji': str(msg_reaction.emoji),
            'count': msg_reaction.count
        })

        server = bot.get_guild(int(server_id))
        rb_channel = server.get_channel_or_thread(rb_setup["channel"])

        author = message.author

        message_embed = discord.Embed(
            url=message.jump_url,
            description=f"[*Jump to message*]({message.jump_url})\n\n" + message.content,
            color=discord.Colour.yellow()
        )

        
        message_embed.set_author(name="@" + author.display_name, icon_url=author.display_avatar.url)

        media_links = get_media_links(message)

        if media_links:
            message_embed.set_image(url=media_links[0]) 

            for i, link in enumerate(media_links[1:], start=1):
                message_embed.add_field(name=f"Media {i + 1}", value=f"[Link]({link})", inline=False)
            


        formatted_reactions = [
            f"`{reaction['count']}` {reaction['emoji']}" 
            for reaction in reactionboard_reactions
        ]

        # count emoji count emoji
        # count emoji count emoji
        concatenated_reactions = []

        for i in range(0, len(formatted_reactions) - 1, 2):
            concatenated_reactions.append(formatted_reactions[i] + '  ' + formatted_reactions[i + 1])

        if len(formatted_reactions) % 2 != 0:
            concatenated_reactions.append(formatted_reactions[-1])

        str_reaction_list = "\n".join(concatenated_reactions)

        if not is_already_in_reactionboard:

            rb_message: discord.Message = await rb_channel.send(str_reaction_list, embed=message_embed)

            rb_messages[server_id][message_id] = rb_message.id
            json_dumpy("reactionboard_messages", rb_messages)

        else:
            rb_message = await rb_channel.fetch_message(rb_messages[server_id][str(message.id)])
            await rb_message.edit(content=str_reaction_list)

        try:
            await rb_message.add_reaction(msg_reaction)
        except:
            pass # in case the emoji is from another server





@bot.command(name="reactionboard", aliases=['rb'])
async def reactionboard_setup(ctx: commands.Context, channel, threshold):
    if not ctx.author.guild_permissions.manage_messages:
        await ctx.send("You don't have the perms.")
        return 
    
    channel = channel[:-1][2:] # trim <# and >

    try:
        channel = int(channel)
        threshold = int(threshold)
    except:
        await ctx.send("i dont know how to set it up with that (Invalid parameters)")
        return

    command_to_log(ctx.author, "reactionboard", ctx.message.content)
    rb_setups = json_loady("reactionboard_setups", True)
    setup = {
        "channel": channel,
        "threshold": threshold
    }
    rb_setups[str(ctx.guild.id)] = setup
    json_dumpy("reactionboard_setups", rb_setups)

    await ctx.send(f"Set reactionboard settings!")


########################################## BATTLES ############################################


class Fighter():
    def __init__(self, health, name, user: discord.Member = None):
        self.health = health
        self.name = name
        self.user = user

@bot.command(name='battle', aliases=["deathbattle", "b", "db"])
async def battle(ctx: commands.Context, opponent: typing.Union[discord.Member, str, None] = None, hp = 100.0):
    command_to_log(ctx.author, "battle", ctx.message.content)
    attacks = json_loady("attacks")
    
    if not opponent:
        opponent = ctx.guild.me

    try:
        hp = float(opponent)
        opponent = ctx.guild.me
    except:
        pass

    if int(hp) == hp:
        hp = int(hp)
     
    if hp > 200:
        await ctx.send("⚠ WARNING: that's a lot of health and the description will probably get cut off.")

    f1_user = ctx.author

    fighter1 = Fighter(hp, f1_user.display_name, f1_user)
    if isinstance(opponent, discord.Member):
        fighter2 = Fighter(hp, opponent.display_name, f1_user)
    else:
        fighter2 = Fighter(hp, opponent)
    
    fighters = [fighter1, fighter2]

    current_attacker_id = random.randint(0, 1)

    attack_history = ""

    ui = f"""
```
{fighter1.name}
HP: {fighter1.health}/{hp}
VS
{fighter2.name}
HP: {fighter2.health}/{hp}
```
"""
    embed = discord.Embed(
        title=f"{fighter1.name} VS {fighter2.name}",
        description=ui,
        color=int("CC0000", 16)
        )

    battle_message = await ctx.send(embed=embed)

    while fighter1.health > 0 and fighter2.health > 0:
        receiver_id = (current_attacker_id + 1) % 2

        attacker = fighters[current_attacker_id]
        receiver = fighters[receiver_id]

        attack = random.choice(attacks)

        try:
            att_dmg = random.randint(*attack["damage"]["attacker"])
            rec_dmg = random.randint(*attack["damage"]["receiver"])
            attacker.health -= att_dmg
            receiver.health -= rec_dmg

        
            attack_desc = attack["description"].format(
                receiver=receiver.name,
                attacker=attacker.name,
                att_dmg=str(abs(att_dmg)),
                rec_dmg=str(abs(rec_dmg))
            )

        except Exception as e:
            print(f"Error: {e}")
            print(attack["description"])
            attack_desc = f"👾 {attacker.name} makes this command error out!"
        
        attack_desc = "`" + attack_desc + "`"
        attack_history += attack_desc + "\n"

        ui = f"""
```
{fighter1.name}
HP: {fighter1.health}/{hp}
VS
{fighter2.name}
HP: {fighter2.health}/{hp}
```
"""

        new_message_content = ui + attack_history

        if len(new_message_content) > 4096:
            await battle_message.reply("Battle description is too long......")
            break

        embed = discord.Embed(
            title=f"{fighter1.name} VS {fighter2.name}",
            description=new_message_content,
            color=int("CC0000", 16)
        )

        await asyncio.sleep(0.8)

        await battle_message.edit(embed=embed)

        current_attacker_id = receiver_id


    winner = fighter1 if fighter1.health > fighter2.health else fighter2
    if fighter1.health < 0 and fighter2.health < 0 or fighter1.health == fighter2.health:
        winner = Fighter(0, "Noone")


    await battle_message.reply(f"> 🏆 {winner.user.mention if winner.user else winner.name} won!")

    if ctx.guild.me.display_name in [f.name for f in fighters]:
        print('i fought')
        if winner.user == ctx.guild.me:
            await ctx.send("I stand undefeated.")
            print('i won')
        elif winner.name == "Noone":
            await ctx.send("well this was a waste of time")
        else:
            print('i lost')
            await ctx.send("https://media.discordapp.net/attachments/1025807938427826351/1353382090321694848/theownerofthisaccount.png")

######################################## SMALL COMMANDS ########################################

@bot.command(name="chance", aliases=['ch'])
async def chance(ctx: commands.Context, *, event = None):
    command_to_log(ctx.author, "chance", ctx.message.content)

    await ctx.send("Calculating the chances of that happening...")
    await asyncio.sleep(2)

    if event == None:
        await ctx.send("specify an event you idoit") 
        return
    event_lower = event.lower()
    seed = str(ctx.author.id) + '_' + event_lower
    random.seed(seed)
    outcome = random.randint(1, 100)
    contains_lovemail = contains_any_substring(event_lower, ["girlfriend", "gf", "wife", "marriage", "married", "relationship", "date", "love", "gf", "bf", "boyfriend"])
    if contains_lovemail and not("not" in event_lower) or not contains_lovemail and "not" in event_lower:
        outcome = random.randint(0, 2)
    await ctx.send(f"Chance of \"{event}\" happening: {outcome}%")
    random.seed()


@bot.command(name="embed", aliases=['e'])
async def send_embed(ctx: commands.Context, *params: str):
    command_to_log(ctx.author, "embed", ctx.message.content)
    embed = discord.Embed()

    param_map = json_loady("misc")["embed_param_map"]

    print(params)
    for param in params:
        key, value = param.split(":", 1)
        if key in param_map:
            attr = param_map[key]
            if attr == "color":
                embed.color = int(value, 16)
            elif attr in ["set_footer", "set_image", "set_thumbnail"]:
                if attr == "set_footer":
                    getattr(embed, attr)(text=value)
                else:
                    getattr(embed, attr)(url=value)
            else:
                setattr(embed, attr, value)

    await ctx.send(embed=embed)



@bot.command(name="joke", aliases=['j'])
async def joke(ctx: commands.Context):
    command_to_log(ctx.author, "joke", ctx.message.content)
    joke_parts = json_loady("jokes", False)
    format, subject, verb1, verb2, object1, object2, adjective, exclamation = [random.choice(joke_parts[thing]) for thing in ["formats", "nouns", "verbs", "verbs", "nouns", "nouns", "adjectives", "exclamations"]]

    joke = format.format(
        subject=subject,
        verb1=verb1, 
        verb2=verb2, 
        object1=object1, 
        object2=object2, 
        adjective=adjective, 
        exclamation=exclamation
    )

    await ctx.send("Oh BOY you are NOT gonna believe this one")
    await asyncio.sleep(1)

    embed = discord.Embed(
        description="***"+joke+"***",
        color=discord.Color.yellow()
    )
    embed.set_footer(text="was this funny")

    await ctx.reply(embed=embed)


@bot.command(name = "reactiontime", aliases=["rt"])
async def reactiontime(ctx: commands.Context):
    message = await ctx.send("React the 🔴 emoji as soon as the square turns green\n⬜")
    await message.add_reaction("🔴")
    await asyncio.sleep(random.uniform(2, 5))
    await message.edit(content="React the 🔴 emoji as soon as the square turns green\n🟩")

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) == '🔴' and reaction.message.id == message.id

    try:
        starttime = time.time()
        reaction, user = await bot.wait_for('reaction_add', timeout=5.0, check=check)
        reaction_time = round(time.time() - starttime, 3)
        is_high_score, high_score = handle_high_score(reaction_time, str(ctx.author.id), "reactiontime")
        await ctx.send(f'Your reaction time is{reaction_time} seconds')

    except asyncio.TimeoutError:
        await ctx.send(f'youre too slow bruh :skull:')


######################################## DEV COMMANDS ########################################

async def dev_check(ctx: commands.Context):
    misc_data = json_loady('misc')
    dev_users = misc_data.get("dev_perm_users", {})
    dev_ids = list(map(int, dev_users.keys()))
    return ctx.author.id in dev_ids

@bot.command(name="setstatus", aliases=['status', 'ss'])
async def setstatus(ctx: commands.Context, *, status: str):
    if not await dev_check(ctx):
        await ctx.send("You are not a dev. grrr")
        return
    
    command_to_log(ctx.author, "setstatus", ctx.message.content)

    await bot.change_presence(activity=discord.Game(name=status))
    await ctx.send(f"Set status to: {status}")
    misc_file = json_loady("misc", True)
    misc_file["status"] = status
    json_dumpy("misc", misc_file)

@bot.command(name="sendfile", aliases=['file', "sf"])
async def sendfile(ctx: commands.Context, file_name: str):
    if not await dev_check(ctx):
        await ctx.send("You are not a dev. grrr")
        return

    command_to_log(ctx.author, "sendfile", ctx.message.content)

    if file_name.endswith("tokens.json"):
        await ctx.send("Nuh uh")
        return

    file = discord.File(file_name)
    await ctx.send(file=file)

@bot.command(name="filetree", aliases=['ft'])
async def sendfiletree(ctx: commands.context):
    command_to_log(ctx.author, "filetree", ctx.message.content)
    filetree = fttt.generate_file_tree(r"C:\Users\HP\programming\Raised EyeBot")
    await ctx.reply(f"```\Raised EyeBot\n{filetree}\n```")



################################### TEST COMMAND #######################################
@bot.command(name="test", aliases=["t"])
async def test(ctx: commands.Context, message_id):
    message = await ctx.fetch_message(message_id)
    reactions = message.reactions
    reactions_str = ', '.join([reaction.emoji for reaction in reactions])
    await ctx.send(reactions_str)
bot.run(TOKENS["discord"])