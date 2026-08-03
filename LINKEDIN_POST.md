# LinkedIn post — final, paste-ready

LinkedIn renders no markdown, so the text below is plain: no asterisks, no
backticks. Copy from inside the fences exactly as-is.

Links
- Live demo: https://frontend-pas-projects-20244f71.vercel.app
- Code:      https://github.com/promzyadiole/Multimodal-Robot-Autonomy

Attach in this order:
1. the belief-vs-truth scatter  (figures/Figure5_2_error_scatter.png)
2. the command graph with the recovery loop lit
3. the LangSmith waterfall
4. the simulation video

Post the scatter first. It is the argument, and it is what stops the scroll.

---

## MAIN VERSION

```
My robot reported that it had arrived at its destination.

It was 15 metres away, in another room.

I spent the last months building a language-grounded autonomy system as a
personal project. You speak or type "go and wait in the dining room", an LLM
resolves the intent, the place name is grounded against a metric map, and ROS 2
Nav2 drives a differential-drive robot there. Open-vocabulary perception with SAM
and CLIP. The whole command policy is a LangGraph state machine, traced end to
end in LangSmith.

The language half worked almost immediately. 54 natural-language commands — bare
names, polite forms, indirect phrasings like "I need you in the kitchen" —
resolved to the correct destination 54 times out of 54.

Then I did the thing most evaluations skip.

Instead of scoring "did it arrive?" using the robot's own localisation estimate,
I scored it against the simulator's ground truth. A source of truth the robot
cannot see.

The navigation stack reported success on 12 of 54 commands.
It had physically arrived on 3.

Ten of the twelve reported successes were false. Median error on those: 6.0
metres. Worst: 15.7 metres. Measured the conventional way, this system looks
nearly four times better than it actually is.

Here is the part I keep thinking about. A reported FAILURE was honest — those
trials sat right on the diagonal between belief and truth. A reported SUCCESS
carried almost no information about where the robot actually was.

The cause is structural. AMCL maintains a belief and corrects it incrementally.
It has no mechanism for noticing that its belief has become wrong by ten metres.
And everything downstream — planner, controller, goal checker — consumes that
belief as fact. The goal checker compares the BELIEVED pose against the goal. So
the robot confidently reports arrival at a place it has never been.

I only found this because the system was built to be interrogated.

That is what I would argue for. LangGraph made the command policy an explicit
state machine rather than a script — understand, navigate, verify, recover,
answer — and the verify node exists specifically to wait for the real outcome
instead of assuming one. Every node records when it ran, how long it took, which
branch it took, and why. LangSmith keeps the same trace offline.

Explainability is usually pitched as a compliance feature. Here it was a
debugging instrument that caught my own stack lying to me.

Three other things the instrumentation surfaced. All of them looked like autonomy
failures. None of them were:

• A caster height I had computed from an assumed radius instead of the measured
  mesh geometry. 13 mm off the floor. The robot balanced on two wheels and
  reached 14% of commanded speed. It presented as a planner failure for days.

• An actuator acceleration limit 18 times below what the controller assumed, so
  every trajectory it simulated was physically unrealisable.

• A map whose perimeter SLAM had never closed, so the planner would happily route
  the robot out of the surveyed area entirely.

Every one of those was my own error in my own robot model. Finding them took
instrumentation, not intuition.

On memory, since people ask: three kinds of state, deliberately separated.
Ephemeral robot state, treated as a cache and never as truth. Episodic history of
poses and outcomes. And a semantic corpus behind a RAG pipeline whose embedding
cache is keyed by the SHA-256 of each chunk's own text rather than its position
in the document — so revising one chapter re-embeds only the paragraphs that
changed. Re-indexing the entire corpus after a restructure cost zero embedding
API calls.

The honest summary: language understanding is solved for this task. Embodiment is
not. Knowing where the body is, and knowing when that knowledge has become false,
is still hard — and it is made harder by an evaluation convention that asks the
estimator to grade its own homework.

The remedy is unglamorous and available to anyone: measure against something the
robot cannot see, and publish both numbers.

Live demo (replays a recorded run, no robot attached):
https://frontend-pas-projects-20244f71.vercel.app

Code: https://github.com/promzyadiole/Multimodal-Robot-Autonomy

ROS 2 Humble · Gazebo · Nav2 · LangGraph · LangChain · LangSmith · OpenAI · SAM ·
CLIP · Pinecone · FastAPI · Next.js

#Robotics #ROS2 #LangGraph #LangChain #ExplainableAI #LLM #ComputerVision #RAG
```

---

## SHORT VERSION — better reach, less depth

```
My robot reported it had arrived. Ground truth said it was 15 metres away, in
another room.

54 natural-language commands. The navigation stack claimed success on 12. It had
actually arrived on 3.

Ten of twelve reported successes were false.

The catch: most evaluations score "did it arrive?" using the robot's own
localisation estimate — asking the estimator to grade its own homework. Score it
against ground truth the robot cannot see and the number falls from 22% to 6%.

I only found it because I built the command policy as a LangGraph state machine
with a verify node that waits for the real outcome, and traced every branch in
LangSmith. Explainability is usually sold as compliance. Here it caught my own
stack lying to me.

Language understanding: 54/54. Embodiment: unsolved.

https://github.com/promzyadiole/Multimodal-Robot-Autonomy

#Robotics #LangGraph #ExplainableAI #ROS2
```

---

## Replies worth preparing

"Why not fuse an IMU / use SLAM with loop closure?"
  Fair, and exactly the future work. Scan-matching odometry, an EKF over
  wheel odometry and IMU, or SLAM with explicit loop closure would each reduce
  drift. But the contribution here is the measurement, not a better localiser —
  and note the odometry in this setup is already near-perfect (0.06% scale
  error). A localiser fed an essentially perfect motion estimate, matching
  against a map that fits the world to within one cell, still diverged by metres.

"So it doesn't work?"
  Correct, and I say so. 6% arrival. The useful result is that the conventional
  metric said 22% and would have been believed.

"Is the demo live?"
  No. It replays a recorded run. Gazebo, ROS 2 and the perception models need a
  persistent machine, and one navigation command takes 25 to 143 seconds — past
  any serverless timeout. The page says so itself.

"Did you fix the divergence?"
  Not yet. I did make the robot admit it: it now reads AMCL's own covariance and
  refuses to claim an arrival the filter cannot support. In the diverged state
  the filter reports a positional spread of 3.36 m against a 0.60 m threshold —
  it knew it was lost, and nothing was reading the signal.
```
