# LinkedIn post — draft

Live demo: https://frontend-pas-projects-20244f71.vercel.app

Attach, in this order: (1) the belief-vs-truth scatter, (2) the LangGraph command
graph with the recovery loop lit, (3) the LangSmith waterfall, (4) the simulation
video. The scatter first — it is the argument, and it stops the scroll.

---

## Main version

My robot reported that it had arrived at its destination.

It was 15 metres away, in another room.

I spent the last months building a language-grounded autonomy system: you speak
or type "go and wait in the dining room", an LLM parses the intent, it is
grounded against a metric map, and ROS 2 Nav2 drives a differential-drive robot
there. Open-vocabulary perception with SAM + CLIP. The whole command policy is a
LangGraph state machine, traced end to end in LangSmith.

The language half worked immediately. 54 natural-language commands — bare names,
polite forms, indirect phrasings, "I need you in the kitchen" — resolved to the
correct destination 54 out of 54 times.

Then I did something most evaluations skip.

Instead of scoring "did it arrive?" using the robot's own localisation estimate,
I scored it against the simulator's ground truth — a source of truth the robot
cannot see.

The navigation stack reported success on 12 of 54 commands.
It had physically arrived on 3.

**10 of the 12 reported successes were false.** Median error on those: 6.0
metres. Worst: 15.7 metres. Measured the conventional way, this system looks
nearly four times better than it is.

Here is what I keep thinking about. A reported *failure* was honest — those
trials sat right on the diagonal between belief and truth. A reported *success*
carried almost no information about where the robot actually was.

The cause: AMCL maintains a belief and corrects it incrementally. It has no
mechanism to notice that its belief has become wrong by ten metres. And every
component downstream — planner, controller, goal checker — consumes that belief
as fact. The goal checker compares the *believed* pose against the goal. So the
robot confidently reports arrival at a place it has never been.

I only found this because the system was built to be interrogated.

That is the part I would argue for. LangGraph made the command policy an
explicit state machine rather than a script — understand → navigate → verify →
recover → answer — and the `verify` node exists specifically to wait for the
real outcome instead of assuming one. Every node records when it ran, how long
it took, which branch it took and *why*. LangSmith keeps the same trace offline.

Explainability is usually pitched as a compliance feature. Here it was a
debugging instrument that caught my own stack lying to me.

A few other things the instrumentation surfaced, all of which looked like
autonomy failures and were none of them:

• A caster height computed from an assumed radius instead of the measured mesh
  geometry. 13 mm off the floor. The robot balanced on two wheels and reached
  14% of commanded speed. It presented as a planner failure for days.
• An actuator acceleration limit 18× below what the controller assumed, so every
  trajectory it simulated was physically unrealisable.
• A map whose perimeter SLAM never closed, so the planner would route the robot
  out of the surveyed area entirely.

On memory: three kinds of state, deliberately kept separate. Ephemeral robot
state, treated as a cache and never as truth. Episodic history of poses and
outcomes. And a semantic corpus behind a RAG pipeline whose embedding cache is
keyed by the SHA-256 of each chunk's own text rather than its position in the
document — so revising one chapter re-embeds only the paragraphs that changed.
Re-indexing the whole corpus after a change cost zero embedding API calls.

The honest summary: language understanding is solved for this task. Embodiment
is not. Knowing where the body is, and knowing when that knowledge has become
false, remains hard — and it is made harder by an evaluation convention that
asks the estimator to grade its own homework.

The fix is unglamorous and available to anyone: measure against something the
robot cannot see, and publish both numbers.

Stack: ROS 2 Humble · Gazebo · Nav2 · LangGraph · LangChain · LangSmith ·
OpenAI · SAM · CLIP · Pinecone · FastAPI · Next.js

#Robotics #ROS2 #LangGraph #LangChain #ExplainableAI #LLM #ComputerVision #RAG

---

## Short version, if you want the scroll-stopper

My robot reported it had arrived. Ground truth said it was 15 metres away, in
another room.

54 language commands. The navigation stack claimed success on 12. It had
actually arrived on 3.

**10 of 12 reported successes were false.**

The catch: most evaluations score "did it arrive?" using the robot's own
localisation estimate — asking the estimator to grade its own homework. Score it
against ground truth the robot cannot see, and the number drops from 22% to 6%.

I only found it because I built the command policy as a LangGraph state machine
with a `verify` node that waits for the real outcome, and traced every branch in
LangSmith. Explainability is usually sold as compliance. Here it caught my own
stack lying to me.

Language understanding: 54/54. Embodiment: unsolved.

#Robotics #LangGraph #ExplainableAI #ROS2

---

## Notes before posting

- If you link the live demo, say plainly that it replays a recorded run. The
  page states this itself, but the post should too, or the first comment will
  ask.
- Expect "why not just fuse an IMU / use SLAM with loop closure?" — a fair
  question and the honest answer is that it is exactly the future work. The
  contribution is the measurement, not a better localiser.
- Do not claim the navigation works. It does not, and the post is stronger for
  saying so.
