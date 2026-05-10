"""
Jednorázový script: Publikace článku o dabérech Crimson Desert na gamefo.cz
"""
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))

import config
import wp_publisher

ARTICLE_TITLE_CS = "Kdo dabuje postavy v Crimson Desert? Hvězdy z Cyberpunku, Baldur's Gate 3 i Final Fantasy"
ARTICLE_TITLE_EN = "Who voices the characters in Crimson Desert? Stars from Cyberpunk, Baldur's Gate 3, and Final Fantasy"

CS_HTML = """
<blockquote class="wp-block-quote"><p>Pearl Abyss odhalil kompletní herecké obsazení pro anglický dabing svého očekávaného akčního RPG Crimson Desert. Studio vsadilo na skutečné herce místo syntetických hlasů a výsledek je impozantní — mezi dabéry najdeme držitele ceny BAFTA i hvězdy z Cyberpunku 2077, Baldur's Gate 3 či Final Fantasy XIV.</p></blockquote>

<hr class="wp-block-separator has-alpha-channel-opacity"/>

<h2>Alec Newman — Kliff (hlavní hrdina)</h2>

<p>Roli Kliffa, vůdce žoldnéřské skupiny Greymanes, ztvárnil skotský herec <strong>Alec Newman</strong>. Fanoušci her ho znají především jako <strong>Adama Smashera z Cyberpunk 2077</strong> a animovaného seriálu Cyberpunk: Edgerunners. Za roli Camerona „Caze" McLearyho ve hře <strong>Still Wakes the Deep</strong> získal v roce 2025 prestižní <strong>cenu BAFTA za nejlepší herecký výkon v hlavní roli</strong>.</p>
<p>Newman má za sebou bohatou kariéru — daboval postavy ve hrách <strong>Xenoblade Chronicles</strong> (Vangarre), <strong>Dragon Age 2</strong> (Sebastian Vael), <strong>Star Wars: The Old Republic</strong> a <strong>Final Fantasy XIV</strong> (Hephaistos, Cagnazzo). Filmovým divákům je známý jako Paul Atreides z televizní minisérie <strong>Duna</strong> (2000) nebo král Aethelred ze seriálu <strong>The Last Kingdom</strong>.</p>

<hr class="wp-block-separator has-alpha-channel-opacity"/>

<h2>Stewart Scudamore — Oongka</h2>

<p>Orkského bojovníka Oongku namluvil londýnský herec <strong>Stewart Scudamore</strong>. V herním světě se proslavil jako <strong>Marneus Calgar ve Warhammer 40,000: Space Marine 2</strong> a <strong>Blackthorne ve Final Fantasy XVI</strong>. Mezi jeho další herní kredity patří <strong>Lies of P: Overture</strong> (Klaus) a chystaná hra <strong>Wuchang: Fallen Feathers</strong> (Ai Nengqi).</p>
<p>Televizní diváci ho mohou znát ze seriálů <strong>Carnival Row</strong> (2019), animovaného seriálu <strong>Arcane</strong> (2021) podle League of Legends nebo historického dramatu <strong>My Lady Jane</strong> (2024).</p>

<hr class="wp-block-separator has-alpha-channel-opacity"/>

<h2>Rebecca Hanssen — Damiane</h2>

<p>Bojovnici Damiane propůjčila hlas skotsko-norská herečka <strong>Rebecca Hanssen</strong>. Její nejznámější herní rolí je <strong>EVE ve Stellar Blade</strong>, jedné z nejúspěšnějších PS5 exkluzivit roku 2024. Ve fenomenálním RPG <strong>Baldur's Gate 3</strong> namluvila hned několik postav — <strong>Alfiru, Yennu a Aurelii</strong>.</p>
<p>Mezi další herní projekty patří <strong>Dying Light: The Beast</strong> (Olivia Jablonski) a <strong>Arknights: Endfield</strong> (Chen Qianyu). V televizním seriálu <strong>The Witcher</strong> od Netflixu ztvárnila královnu Meve.</p>

<hr class="wp-block-separator has-alpha-channel-opacity"/>

<h2>Peter Bramhill — Yann</h2>

<p><strong>Peter Bramhill</strong> propůjčil hlas postavě Yanna. Tento britský herec je v herním světě legendou — už přes <strong>sedm let dabuje Thancreda Waterse ve Final Fantasy XIV</strong> napříč mnoha rozšířeními, což z něj dělá jednoho z nejdéle sloužících hlasových herců v sérii. Mezi jeho další herní role patří <strong>král Cailan z Dragon Age: Origins</strong> a <strong>Egil z Xenoblade Chronicles</strong>.</p>

<hr class="wp-block-separator has-alpha-channel-opacity"/>

<h2>Emily Barber — Naira</h2>

<p>Postavu Nairy namluvila <strong>Emily Barber</strong>, anglická herečka známá především z divadelních prken londýnského West Endu. Televizní diváci ji znají ze seriálů <strong>Bridgerton</strong> (role Tessy), <strong>Industry</strong> a <strong>MobLand</strong>. V herním průmyslu je relativní nováčkou — Crimson Desert představuje její první velkou herní roli.</p>

<hr class="wp-block-separator has-alpha-channel-opacity"/>

<h2>Alastair Parker — Myurdin</h2>

<p>Hlavního antagonistu Myurdina, vůdce skupiny Black Bears, namluvil zkušený <strong>Alastair Parker</strong>. Hráči RPG her ho dobře znají — daboval <strong>Blackwalla v Dragon Age: Inquisition</strong>, jednoho z nejoblíbenějších companionů ve hře. Mezi jeho další herní kredity patří <strong>Castlevania: Lords of Shadow 2</strong> (Nergal Meslamstea), <strong>GreedFall</strong> (Commander Torsten), <strong>The Witcher 3: Wild Hunt</strong>, <strong>Fable III</strong> a <strong>Mass Effect 3</strong>.</p>

<hr class="wp-block-separator has-alpha-channel-opacity"/>

<h2>Autentický přístup Pearl Abyss</h2>

<p>Studio Pearl Abyss pod vedením režiséra Marka Healyho zvolilo netradiční přístup k nahrávání. Herci fyzicky předváděli bojové scény, aby zachytili autentické zvuky námahy a bolesti. Alec Newman například založil Kliffův hluboký, ostražitý hlas na svém zesnulém nevlastním otci, čímž dodal postavě mimořádnou emocionální hloubku.</p>
<p><strong>Crimson Desert</strong> vychází na PC a konzole a slibuje rozsáhlý open-world zážitek na kontinentu Pywel, kde kvalitní dabing hraje klíčovou roli v příběhovém prožitku.</p>

<h2>Zdroje</h2>
<ul>
<li><a href="https://gamerant.com/crimson-desert-voice-actors-names-characters/" target="_blank" rel="noopener">gamerant.com</a></li>
<li><a href="https://fandomwire.com/crimson-desert-voice-actors-list-revealed/" target="_blank" rel="noopener">fandomwire.com</a></li>
<li><a href="https://www.allkeyshop.com/blog/en-us/crimson-desert-voice-cast-revealed-news-r/" target="_blank" rel="noopener">allkeyshop.com</a></li>
<li><a href="https://game8.co/articles/latest/crimson-desert-reveals-voice-cast-featuring-bg3-arcane-and-cyberpunk-2077-stars" target="_blank" rel="noopener">game8.co</a></li>
</ul>
"""

EN_HTML = """
<blockquote class="wp-block-quote"><p>Pearl Abyss has revealed the full English voice cast for its highly anticipated action RPG Crimson Desert. The studio opted for real human talent over synthetic voices, and the result is impressive — the cast includes a BAFTA winner and stars from Cyberpunk 2077, Baldur's Gate 3, and Final Fantasy XIV.</p></blockquote>

<hr class="wp-block-separator has-alpha-channel-opacity"/>

<h2>Alec Newman — Kliff (protagonist)</h2>

<p>The role of Kliff, leader of the Greymanes mercenary group, is portrayed by Scottish actor <strong>Alec Newman</strong>. Gamers know him best as <strong>Adam Smasher from Cyberpunk 2077</strong> and the animated series Cyberpunk: Edgerunners. For his role as Cameron "Caz" McLeary in <strong>Still Wakes the Deep</strong>, he won the prestigious <strong>2025 BAFTA Games Award for Performer in a Leading Role</strong>.</p>
<p>Newman has an extensive career — he voiced characters in <strong>Xenoblade Chronicles</strong> (Vangarre), <strong>Dragon Age 2</strong> (Sebastian Vael), <strong>Star Wars: The Old Republic</strong>, and <strong>Final Fantasy XIV</strong> (Hephaistos, Cagnazzo). Film audiences may recognize him as Paul Atreides from the <strong>Dune</strong> TV miniseries (2000) or King Aethelred from <strong>The Last Kingdom</strong>.</p>

<hr class="wp-block-separator has-alpha-channel-opacity"/>

<h2>Stewart Scudamore — Oongka</h2>

<p>The orc warrior Oongka is voiced by London-born actor <strong>Stewart Scudamore</strong>. In the gaming world, he's best known as <strong>Marneus Calgar in Warhammer 40,000: Space Marine 2</strong> and <strong>Blackthorne in Final Fantasy XVI</strong>. His other gaming credits include <strong>Lies of P: Overture</strong> (Klaus) and the upcoming <strong>Wuchang: Fallen Feathers</strong> (Ai Nengqi).</p>
<p>TV viewers may know him from <strong>Carnival Row</strong> (2019), the animated series <strong>Arcane</strong> (2021) based on League of Legends, or the historical drama <strong>My Lady Jane</strong> (2024).</p>

<hr class="wp-block-separator has-alpha-channel-opacity"/>

<h2>Rebecca Hanssen — Damiane</h2>

<p>The fighter Damiane is voiced by Scottish-Norwegian actress <strong>Rebecca Hanssen</strong>. Her most famous gaming role is <strong>EVE in Stellar Blade</strong>, one of the most successful PS5 exclusives of 2024. In the phenomenal RPG <strong>Baldur's Gate 3</strong>, she voiced multiple characters — <strong>Alfira, Yenna, and Aurelia</strong>.</p>
<p>Her other gaming projects include <strong>Dying Light: The Beast</strong> (Olivia Jablonski) and <strong>Arknights: Endfield</strong> (Chen Qianyu). In Netflix's <strong>The Witcher</strong> TV series, she portrayed Queen Meve.</p>

<hr class="wp-block-separator has-alpha-channel-opacity"/>

<h2>Peter Bramhill — Yann</h2>

<p><strong>Peter Bramhill</strong> voices the character Yann. This British actor is a legend in the gaming world — he has been voicing <strong>Thancred Waters in Final Fantasy XIV for over seven years</strong> across multiple expansions, making him one of the longest-serving voice actors in the franchise. His other gaming roles include <strong>King Cailan from Dragon Age: Origins</strong> and <strong>Egil from Xenoblade Chronicles</strong>.</p>

<hr class="wp-block-separator has-alpha-channel-opacity"/>

<h2>Emily Barber — Naira</h2>

<p>Naira is voiced by <strong>Emily Barber</strong>, an English actress primarily known from the London West End stage. TV audiences know her from <strong>Bridgerton</strong> (as Tessa), <strong>Industry</strong>, and <strong>MobLand</strong>. She's relatively new to the gaming industry — Crimson Desert represents her first major gaming role.</p>

<hr class="wp-block-separator has-alpha-channel-opacity"/>

<h2>Alastair Parker — Myurdin</h2>

<p>The main antagonist Myurdin, leader of the Black Bears, is voiced by veteran <strong>Alastair Parker</strong>. RPG fans know him well — he voiced <strong>Blackwall in Dragon Age: Inquisition</strong>, one of the game's most beloved companions. His other gaming credits include <strong>Castlevania: Lords of Shadow 2</strong> (Nergal Meslamstea), <strong>GreedFall</strong> (Commander Torsten), <strong>The Witcher 3: Wild Hunt</strong>, <strong>Fable III</strong>, and <strong>Mass Effect 3</strong>.</p>

<hr class="wp-block-separator has-alpha-channel-opacity"/>

<h2>Pearl Abyss' authentic approach</h2>

<p>Pearl Abyss, under director Mark Healy, took an unconventional approach to recording. Actors physically performed combat scenes to capture authentic sounds of exertion and pain. Alec Newman, for instance, based Kliff's deep, watchful growl on his late stepfather, adding extraordinary emotional depth to the character.</p>
<p><strong>Crimson Desert</strong> launches on PC and consoles, promising an expansive open-world experience on the continent of Pywel, where quality voice acting plays a crucial role in the narrative experience.</p>

<h2>Sources</h2>
<ul>
<li><a href="https://gamerant.com/crimson-desert-voice-actors-names-characters/" target="_blank" rel="noopener">gamerant.com</a></li>
<li><a href="https://fandomwire.com/crimson-desert-voice-actors-list-revealed/" target="_blank" rel="noopener">fandomwire.com</a></li>
<li><a href="https://www.allkeyshop.com/blog/en-us/crimson-desert-voice-cast-revealed-news-r/" target="_blank" rel="noopener">allkeyshop.com</a></li>
<li><a href="https://game8.co/articles/latest/crimson-desert-reveals-voice-cast-featuring-bg3-arcane-and-cyberpunk-2077-stars" target="_blank" rel="noopener">game8.co</a></li>
</ul>
"""

SEO_TAGS = [
    "Crimson Desert",
    "Pearl Abyss",
    "voice actors",
    "dabéři",
    "Alec Newman",
    "Rebecca Hanssen",
    "Stewart Scudamore",
    "RPG",
]


def main():
    if not config.is_wp_configured():
        print("ERROR: WordPress neni nakonfigurovan")
        sys.exit(1)

    print("=" * 60)
    print("PUBLISHING: Crimson Desert voice actors article")
    print("=" * 60)

    # 1. Hledání featured image přes RAWG
    featured_image_id = None
    try:
        import requests
        if config.RAWG_API_KEY:
            resp = requests.get(
                'https://api.rawg.io/api/games',
                params={'key': config.RAWG_API_KEY, 'search': 'Crimson Desert', 'page_size': 1},
                timeout=10,
            )
            if resp.status_code == 200:
                results = resp.json().get('results', [])
                if results and results[0].get('background_image'):
                    image_url = results[0]['background_image']
                    print(f"RAWG image found: {image_url}")
                    media_id, _, err = wp_publisher.upload_media(image_url, title="Crimson Desert")
                    if media_id:
                        featured_image_id = media_id
                        print(f"Featured image uploaded (ID: {media_id})")
                    else:
                        print(f"Image upload failed: {err}")
    except Exception as e:
        print(f"RAWG search error: {e}")

    # 2. Publish CZ
    print("\nPublishing CZ version...")
    cs_content = wp_publisher._to_gutenberg_blocks(CS_HTML.strip())
    cs_result, cs_err = wp_publisher.create_draft(
        title=ARTICLE_TITLE_CS,
        content=cs_content,
        category_ids=[9],  # Zprávy
        tag_names=SEO_TAGS,
        lang='cs',
        featured_image_id=featured_image_id,
        status_tag='info',
        source_info='https://gamerant.com/crimson-desert-voice-actors-names-characters/\nhttps://fandomwire.com/crimson-desert-voice-actors-list-revealed/',
        status='draft',
        focus_keyword='Crimson Desert',
    )

    if cs_err:
        print(f"CZ PUBLISH ERROR: {cs_err}")
        sys.exit(1)

    print(f"CZ published: {cs_result['view_url']}")
    print(f"CZ edit:      {cs_result['edit_url']}")

    # 3. Publish EN
    print("\nPublishing EN version...")
    en_content = wp_publisher._to_gutenberg_blocks(EN_HTML.strip())
    en_result, en_err = wp_publisher.create_draft(
        title=ARTICLE_TITLE_EN,
        content=en_content,
        category_ids=[12],  # News
        tag_names=SEO_TAGS,
        lang='en',
        featured_image_id=featured_image_id,
        status_tag='info',
        source_info='https://gamerant.com/crimson-desert-voice-actors-names-characters/\nhttps://fandomwire.com/crimson-desert-voice-actors-list-revealed/',
        status='draft',
        focus_keyword='Crimson Desert',
    )

    if en_err:
        print(f"EN PUBLISH ERROR: {en_err}")
    else:
        print(f"EN published: {en_result['view_url']}")
        print(f"EN edit:      {en_result['edit_url']}")

        # Link translations
        link_ok, link_err = wp_publisher.link_translations(cs_result['id'], en_result['id'])
        if link_ok:
            print("CZ/EN linked OK")
        else:
            print(f"Translation link failed: {link_err}")

    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)


if __name__ == '__main__':
    main()
