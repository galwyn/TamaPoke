// How big the pet stands on the main screen.
//
// drawPmdActM() aimed for ~170 px but divided by the sprite's CANVAS height,
// and a PMD canvas is mostly transparent padding: a typical creature is 25 px
// tall inside a 40-56 px canvas, so it was drawn ~92 px tall on a 466 px
// panel. Reported from a board ("the pictures are too small").
//
// This checks every species on the card, not the one that was reported.
#include "Arduino.h"
#include "Arduino_GFX_Library.h"
#include "Preferences.h"
#include "pet.h"
#include "party.h"
#include "sdmon.h"
#include <cstdio>
#include <cstring>
#include <algorithm>
#include <vector>
uint32_t g_seed=7; FakeSerial Serial; FakeESP ESP; FakeWire Wire;
volatile int g_touchX=0,g_touchY=0; volatile bool g_touchDown=false;
uint32_t millis(){return 0;}
void FakeESP::restart(){exit(0);}
int FakeSerial::available(){return 0;} String FakeSerial::readStringUntil(char){return String("");}
void emuSetSpriteDir(const char *);
static int bad=0;
static void ck(bool ok,const char*w){printf("%s  %s\n",ok?"PASS":"FAIL",w); if(!ok)bad++;}

int main(){
  emuSetSpriteDir(SPRITE_DIR);
  int loaded = 0, small = 0, tooTall = 0, tooTallAct = 0, badTop = 0, tooWide = 0;
  int minH = 999, worstDex = 0;
  std::vector<int> heights;
  for (int dex = 1; dex <= 151; dex++) {
    PmdMon m;
    if (!m.load(dex, false)) continue;
    loaded++;
    for (int a = 0; a < PMD_NACTS; a++)
      if (m.has(a) && !(m.acts[a].top < m.acts[a].base)) badTop++;
    const PmdAct &idle = m.acts[PMD_IDLE];
    int s = petPmdScale(m, PMD_IDLE);
    int h = pmdVisH(idle) * s;
    heights.push_back(h);
    if (h < minH) { minH = h; worstDex = dex; }
    if (h < 100) small++;  // flat creatures (Kabuto, 14 rows) stop at PET_MAX_SCALE: 112 px
    if (h > PET_TARGET_H) tooTall++;
    if (idle.w * s > 466) tooWide++;
    for (int a = 0; a < PMD_NACTS; a++)
      if (m.has(a) && pmdAboveGround(m.acts[a]) * petPmdScale(m, a) > PET_MAX_H) tooTallAct++;
  }
  std::sort(heights.begin(), heights.end());
  int median = heights.empty() ? 0 : heights[heights.size() / 2];
  printf("species loaded: %d, shortest standing pet: %d px (dex %d), median %d px\n", loaded, minH, worstDex, median);
  // Guenael, 2026-11-26: 170 px looked only a little bigger on the board; fill
  // the room the layout has, which is 190 px above the ground line.
  ck(median >= 170, "the median standing pet is at least 170 px tall");
  ck(loaded >= 151, "every Kanto sprite is on the card");
  ck(badTop == 0, "each action knows its top drawn row, above its feet");
  ck(small == 0, "no standing pet is drawn under 100 px tall (was 62 px before)");
  ck(tooTall == 0, "no standing pet is drawn over the PET_TARGET_H target");
  ck(tooWide == 0, "no standing pet's canvas is wider than the panel");
  ck(tooTallAct == 0, "no action rises more than PET_MAX_H above the ground line");
  return bad ? 1 : 0;
}
