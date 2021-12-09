from mojo.subscriber import registerSubscriberEvent, roboFontSubscriberEventRegistry

WurstSchreiberDefaultKey = "com.asaumierdemers.WurstSchreiber"

if __name__ == '__main__':
    if f"{WurstSchreiberDefaultKey}.updateGlyphEditor" not in roboFontSubscriberEventRegistry:
        registerSubscriberEvent(
            subscriberEventName=f"{WurstSchreiberDefaultKey}.updateGlyphEditor",
            methodName="wurstSchreiverUpdateGlyphEditor",
            lowLevelEventNames=[f"{WurstSchreiberDefaultKey}.updateGlyphEditor"],
            dispatcher="roboFont",
            delay=0.02,
        )

        registerSubscriberEvent(
            subscriberEventName=f"{WurstSchreiberDefaultKey}.removeWurst",
            methodName="wurstSchreiverRemoveWurst",
            lowLevelEventNames=[f"{WurstSchreiberDefaultKey}.removeWurst"],
            dispatcher="roboFont",
            delay=0,
        )
