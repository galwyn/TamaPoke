// SNAP: the console command that sends the frame to a computer. What it sends
// has to be the framebuffer pixel for pixel, or a screenshot is worse than none:
// it would be trusted. This decodes the reply independently of tools/snap.py and
// compares every pixel with the buffer.
#include "Arduino.h"
#include "Arduino_GFX_Library.h"
#include "Preferences.h"
#include "pet.h"
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
#include <unistd.h>
uint32_t g_seed=3; FakeSerial Serial; FakeESP ESP; FakeWire Wire;
volatile int g_touchX=0,g_touchY=0; volatile bool g_touchDown=false;

static std::vector<std::string> gIn;
static size_t gAt = 0;
int FakeSerial::available(){ return gAt < gIn.size() ? 1 : 0; }
String FakeSerial::readStringUntil(char){
  if (gAt >= gIn.size()) return String("");
  return String(gIn[gAt++].c_str());
}
void FakeESP::restart(){}

void setup(); void handleSerial();
extern Arduino_Canvas *gfx;
extern bool screenOff;

static int bad=0;
static void ck(bool ok,const char*w){printf("%s  %s\n",ok?"PASS":"FAIL",w); if(!ok)bad++;}

static std::string runConsole(const std::string &cmd){
  gIn = {cmd}; gAt = 0;
  char path[] = "/tmp/tamapoke_snap_XXXXXX";
  int fd = mkstemp(path);
  if (fd < 0) return "";
  fflush(stdout);
  int saved = dup(fileno(stdout));
  dup2(fd, fileno(stdout));
  handleSerial();
  fflush(stdout);
  dup2(saved, fileno(stdout));
  close(saved);
  lseek(fd, 0, SEEK_SET);
  std::string out;
  char b[4096]; ssize_t n;
  while ((n = read(fd, b, sizeof(b))) > 0) out.append(b, (size_t)n);
  close(fd);
  remove(path);
  return out;
}

static std::vector<std::string> lines(const std::string &s){
  std::vector<std::string> v; std::string cur;
  for (char c : s) { if (c=='\n') { v.push_back(cur); cur.clear(); } else if (c!='\r') cur+=c; }
  if (!cur.empty()) v.push_back(cur);
  return v;
}

struct Decoded { bool ok=false; std::string header; std::vector<uint16_t> px; uint32_t sent=0, computed=0; };

static Decoded decode(const std::string &out){
  Decoded d; auto v = lines(out);
  size_t i = 0;
  while (i < v.size() && v[i].rfind("SNAP 1 ",0) != 0) i++;
  if (i == v.size()) return d;
  d.header = v[i++];
  int w=0,h=0; sscanf(d.header.c_str(), "SNAP 1 %d %d", &w, &h);
  uint32_t sum = 2166136261u;
  for (int y=0; y<h; y++, i++) {
    if (i >= v.size() || v[i].size() % 6) return d;
    int x = 0;
    for (size_t k=0; k<v[i].size(); k+=6) {
      int run = (int)strtol(v[i].substr(k,2).c_str(), nullptr, 16);
      uint16_t c = (uint16_t)strtol(v[i].substr(k+2,4).c_str(), nullptr, 16);
      if (run < 1) return d;
      for (int r=0; r<run; r++, x++) {
        d.px.push_back(c);
        sum = (sum ^ (c & 0xFF)) * 16777619u;
        sum = (sum ^ (c >> 8)) * 16777619u;
      }
    }
    if (x != w) return d;
  }
  if (i >= v.size() || v[i].rfind("SNAPEND ",0) != 0) return d;
  d.sent = (uint32_t)strtoul(v[i].c_str()+8, nullptr, 16);
  d.computed = sum;
  d.ok = true;
  return d;
}

static bool samePixels(const Decoded &d){
  const uint16_t *fb = gfx->buffer();
  if (d.px.size() != 466u*466u) return false;
  for (size_t i=0;i<d.px.size();i++) if (d.px[i] != fb[i]) return false;
  return true;
}

int main(){
  setup();

  // a frame with long runs, single pixels in the corners, and one row where no
  // two neighbours match -- the shortest and longest lines the format produces
  gfx->fillScreen(0x1234);
  gfx->fillRect(10, 20, 300, 40, 0xF800);
  gfx->fillRect(0, 0, 1, 1, 0x0001);
  gfx->fillRect(465, 465, 1, 1, 0xFFFE);
  for (int x=0; x<466; x++) gfx->fillRect(x, 200, 1, 1, (x & 1) ? 0x07E0 : 0x001F);

  std::string out = runConsole("SNAP");
  Decoded d = decode(out);
  ck(d.ok, "SNAP replies with a header, 466 whole rows and an end line");
  ck(d.header.rfind("SNAP 1 466 466 ",0) == 0, "the header names the size");
  ck(d.header.find(" fw=") != std::string::npos, "and the firmware version");
  ck(d.header.find(" md5=") != std::string::npos, "and which build is running");
  ck(d.header.find(" screen=on") != std::string::npos, "and that the screen is on");
  ck(samePixels(d), "every pixel matches the framebuffer");
  ck(d.ok && d.sent == d.computed, "the checksum matches the pixels");

  screenOff = true;
  Decoded off = decode(runConsole("SNAP"));
  ck(off.header.find(" screen=off") != std::string::npos, "a screen switched off by PWR is reported");
  screenOff = false;

  return bad ? 1 : 0;
}
