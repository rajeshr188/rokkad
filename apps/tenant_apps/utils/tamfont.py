# python Font Render Tamil Noto Font
import os
import re
import sys


class tamfont:
    def __init__(self, txt):
        self.txt = txt

    def tam(self):
        txt = self.txt + " "
        # txt = txt

        dump = []
        # ே ெ ை ெள  எழுத்துகள் மாற்றம் செய்தல்
        for index, unik in enumerate(txt):
            if (
                ord(unik) == 3014
                or ord(unik) == 3015
                or ord(unik) == 3016
                or ord(unik) == 3018
                or ord(unik) == 3019
                or ord(unik) == 3020
            ):
                dump.insert(index - 1, unik)
            else:
                dump.insert(index, unik)

        txt = dump
        output = ""
        for index, unik in enumerate(txt):
            # சு
            if ord(txt[index]) == 2970 and ord(txt[index + 1]) == 3009:
                output = output + "\u0C15"
                # சூ
            elif ord(txt[index]) == 2970 and ord(txt[index + 1]) == 3010:
                output = output + "\u0C16"

                # ஜீ
            elif ord(txt[index]) == 2972 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c1a"

                # ஜு
            elif ord(txt[index]) == 2972 and ord(txt[index + 1]) == 3009:
                output = output + "\u0b9c\u0bc1"
            # ஜூ
            elif ord(txt[index]) == 2972 and ord(txt[index + 1]) == 3010:
                output = output + "\u0b9c\u0bc2"

            # கீ
            elif ord(txt[index]) == 2965 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c1b"

            # கு
            elif ord(txt[index]) == 2965 and ord(txt[index + 1]) == 3009:
                output = output + "\u0c1e"

            # கூ
            elif ord(txt[index]) == 2965 and ord(txt[index + 1]) == 3010:
                output = output + "\u0c1f"

            # லி
            elif ord(txt[index]) == 2994 and ord(txt[index + 1]) == 3007:
                continue

            # லீ
            elif ord(txt[index]) == 2994 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c21"

            # லு
            elif ord(txt[index]) == 2994 and ord(txt[index + 1]) == 3009:
                output = output + "\u0c28"

            # லூ
            elif ord(txt[index]) == 2994 and ord(txt[index + 1]) == 3010:
                output = output + "\u0c29"

            # ளீ
            elif ord(txt[index]) == 2995 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c22"

            # ளு
            elif ord(txt[index]) == 2995 and ord(txt[index + 1]) == 3009:
                output = output + "\u0c26"

            # ளூ
            elif ord(txt[index]) == 2995 and ord(txt[index + 1]) == 3010:
                output = output + "\u0c27"

            # மீ
            elif ord(txt[index]) == 2990 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c2A"

            # மு
            elif ord(txt[index]) == 2990 and ord(txt[index + 1]) == 3009:
                output = output + "\u0c2b"

            # மூ
            elif ord(txt[index]) == 2990 and ord(txt[index + 1]) == 3010:
                output = output + "\u0c2c"

            # ழீ
            elif ord(txt[index]) == 2996 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c23"

            # ழு
            elif ord(txt[index]) == 2996 and ord(txt[index + 1]) == 3009:
                output = output + "\u0c24"

            # ழூ
            elif ord(txt[index]) == 2996 and ord(txt[index + 1]) == 3010:
                output = output + "\u0c25"

            # ஙீ
            elif ord(txt[index]) == 2969 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c2d"

            # ஙு
            elif ord(txt[index]) == 2969 and ord(txt[index + 1]) == 3009:
                output = output + "\u0c2e"

            # ஙூ
            elif ord(txt[index]) == 2969 and ord(txt[index + 1]) == 3010:
                output = output + "\u0c2f"

            # நீ
            elif ord(txt[index]) == 2984 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c30"

            # நு
            elif ord(txt[index]) == 2984 and ord(txt[index + 1]) == 3009:
                output = output + "\u0c37"

            # நூ
            elif ord(txt[index]) == 2984 and ord(txt[index + 1]) == 3010:
                output = output + "\u0c38"

            # னீ
            elif ord(txt[index]) == 2985 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c32"

            # னு
            elif ord(txt[index]) == 2985 and ord(txt[index + 1]) == 3009:
                output = output + "\u0c33"

            # னூ
            elif ord(txt[index]) == 2985 and ord(txt[index + 1]) == 3010:
                output = output + "\u0c34"

            # ணீ
            elif ord(txt[index]) == 2979 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c31"

            # ணு
            elif ord(txt[index]) == 2979 and ord(txt[index + 1]) == 3009:
                output = output + "\u0c35"

            # ணூ
            elif ord(txt[index]) == 2979 and ord(txt[index + 1]) == 3010:
                output = output + "\u0c36"

            # ஞீ
            elif ord(txt[index]) == 2974 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c39"

            # ஞு
            elif ord(txt[index]) == 2974 and ord(txt[index + 1]) == 3009:
                output = output + "\u0c3A"

            # ஞூ
            elif ord(txt[index]) == 2974 and ord(txt[index + 1]) == 3010:
                output = output + "\u0c3B"

            # பீ
            elif ord(txt[index]) == 2986 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c3c"

            # பு
            elif ord(txt[index]) == 2986 and ord(txt[index + 1]) == 3009:
                output = output + "\u0c3d"

            # பூ
            elif ord(txt[index]) == 2986 and ord(txt[index + 1]) == 3010:
                output = output + "\u0c3e"

            # ரீ
            elif ord(txt[index]) == 2992 and ord(txt[index + 1]) == 3008:
                if ord(txt[index - 2]) == 3000 and ord(txt[index - 1]) == 3021:
                    continue
                else:
                    output = output + "\u0c3f"

            # ரு
            elif ord(txt[index]) == 2992 and ord(txt[index + 1]) == 3009:
                output = output + "\u0c43"

            # ரூ
            elif ord(txt[index]) == 2992 and ord(txt[index + 1]) == 3010:
                output = output + "\u0c44"

            # றீ
            elif ord(txt[index]) == 2993 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c40"

            # று
            elif ord(txt[index]) == 2993 and ord(txt[index + 1]) == 3009:
                output = output + "\u0c41"

            # றூ
            elif ord(txt[index]) == 2993 and ord(txt[index + 1]) == 3010:
                output = output + "\u0c42"

            # டி
            elif ord(txt[index]) == 2975 and ord(txt[index + 1]) == 3007:
                output = output + "\u0c4b"
            # டீ
            elif ord(txt[index]) == 2975 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c4c"

            # டு
            elif ord(txt[index]) == 2975 and ord(txt[index + 1]) == 3009:
                output = output + "\u0c4d"

            # டூ
            elif ord(txt[index]) == 2975 and ord(txt[index + 1]) == 3010:
                output = output + "\u0c4e"

            # தீ
            elif ord(txt[index]) == 2980 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c4A"

            # து
            elif ord(txt[index]) == 2980 and ord(txt[index + 1]) == 3009:
                output = output + "\u0c4f"

            # தூ
            elif ord(txt[index]) == 2980 and ord(txt[index + 1]) == 3010:
                output = output + "\u0c50"
            # வீ
            elif ord(txt[index]) == 2997 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c55"

            # வு
            elif ord(txt[index]) == 2997 and ord(txt[index + 1]) == 3009:
                output = output + "\u0c56"

            # வூ
            elif ord(txt[index]) == 2997 and ord(txt[index + 1]) == 3010:
                output = output + "\u0c57"

            # யீ
            elif ord(txt[index]) == 2991 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c58"

            # யு
            elif ord(txt[index]) == 2991 and ord(txt[index + 1]) == 3009:
                output = output + "\u0c59"

            # யூ
            elif ord(txt[index]) == 2991 and ord(txt[index + 1]) == 3010:
                output = output + "\u0c5a"

            # ஸி
            elif ord(txt[index]) == 3000 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c47"

            # ஸீ
            elif ord(txt[index]) == 3000 and ord(txt[index + 1]) == 3009:
                output = output + "\u0c48"
            # ஸ்ரீ
            elif (
                ord(txt[index]) == 3000
                and ord(txt[index + 1]) == 3021
                and ord(txt[index + 2]) == 2992
                and ord(txt[index + 3]) == 3008
            ):
                output = output + "\u0c46"

            # ஷீ
            elif ord(txt[index]) == 2999 and ord(txt[index + 1]) == 3008:
                output = output + "\u0c49"
            # ஷி
            elif ord(txt[index]) == 2999 and ord(txt[index + 1]) == 3007:
                output = output + "\u0bb7"

            # dot
            elif ord(txt[index]) == 3021:
                output = output + "\u0bcd"

                # skip ி மற்றும் ீ குறியீடு (இ-ஈ)
            elif (
                ord(txt[index]) == 3007
                or ord(txt[index]) == 3008
                or ord(txt[index]) == 3009
                or ord(txt[index]) == 3010
            ):
                # லி
                if ord(txt[index]) == 3007 and ord(txt[index - 1]) == 2994:
                    output = output + "\u0c20"
                # டி skip ி
                elif ord(txt[index]) == 3007 and ord(txt[index - 1]) == 2975:
                    continue
                # ஷு
                elif ord(txt[index]) == 3009 and ord(txt[index - 1]) == 2999:
                    output = output + "\u0bc1"
                # ஷூ
                elif ord(txt[index]) == 3010 and ord(txt[index - 1]) == 2999:
                    output = output + "\u0bc2"

                elif ord(txt[index]) == 3007:
                    output = output + "\u0bbf"
                    continue

            else:
                g = txt[index].encode("unicode-escape").decode()
                output = output + g.encode().decode("unicode-escape")

        return output
