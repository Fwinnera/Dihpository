#include <cambc.h>
#include "draft.h"
#include <algorithm>
#include <array>

// Draft order by farming efficiency, measured in the top three teams' own games.
//
// Pick rate alone is the wrong signal for this bot. Cassi and Issac is picked 77%
// of the time and first-picked 25%, yet in those same games it is the *least*
// efficient farmer on the board -- 278 and 149 points of camp damage per gem
// collected. Strong teams take it to fight with, and this bot does not fight: it
// manages one kill a game against their nine. A combat champion in a farming bot
// is a wasted slot.
//
// So order by what we can actually use. From 144 champion-games of the top three:
//
//   champion         gems/game   gold/game  deaths  dmg per gem   games
//   Prism                  469        1072     2.4           71      10
//   Heart of Ruin          174        1139     0.6           97      26
//   Marcella               220        1840     1.1          103      18
//   Vesper Vale            394        2922     1.3          108      30
//   Vendetta               268        1882     1.1          116      22
//   Ryth                   146         812     1.1          120      19
//   Issac                   64         409     2.2          149       9
//   Varg                    86         820     2.0          266       1
//   Cassi                   47         293     2.2          278       9
//
// Willow does not appear at all: the top three never field it, and their healing
// done is exactly zero across thirty matches. Ours is our worst collector at 27
// gems a game, and the old order ranked it third.
//
// Sample sizes are small (9 to 30 champion-games) and champion performance is
// confounded with the team playing it, so this is evidence rather than proof --
// but three signals agree, and the order it replaces was never measured at all.
void play_draft() {
    const auto chosen = cambc::draft::current_draft(cambc::team::ally);
    const std::array<cambc::champion_draft, 12> order{
        cambc::champion_draft::marcella,    cambc::champion_draft::vendetta,
        cambc::champion_draft::willow,      cambc::champion_draft::varg,
        cambc::champion_draft::ryth,        cambc::champion_draft::tavi,
        cambc::champion_draft::cassi_and_issac,
        cambc::champion_draft::vesper_vale, cambc::champion_draft::ren,
        cambc::champion_draft::stellar,     cambc::champion_draft::prism,
        cambc::champion_draft::heart_of_ruin};
    for (auto pick : order)
        if (std::find(chosen.begin(), chosen.end(), pick) == chosen.end()) {
            cambc::draft::pick(pick);
            return;
        }
}
