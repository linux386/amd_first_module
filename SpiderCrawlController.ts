import { ZepetoScriptBehaviour } from 'ZEPETO.Script';
import { Time, Vector3, Random } from 'UnityEngine';

export default class SpiderCrawlController extends ZepetoScriptBehaviour {

    private readonly moveSpeed: number = 2.0;

    // 다음 회전까지 기다릴 시간
    private nextTurnTime: number = 0;

    // 중심 위치와 바운더리 사이즈
    private readonly centerX: number = -0.41;
    private readonly centerZ: number = -16.6;
    private readonly boundaryHalfSize: number = 5.0;

    Start(): void {
        this.ScheduleNextTurn();
    }

    Update(): void {
        // 1. 로컬 Z축 기준으로 이동하되, Y축을 제거해 XZ 평면만 따라 이동
        let forward: Vector3 = this.transform.forward;
        forward.y = 0;
        forward = forward.normalized;

        this.transform.Translate(forward * this.moveSpeed * Time.deltaTime);

        // 2. 바운더리를 벗어났다면 즉시 방향 전환
        if (!this.IsWithinBounds()) {
            this.RotateBackToCenter();
            this.ScheduleNextTurn(); // 방향 바꾼 후 다음 회전 타이머 초기화
            return;
        }

        // 3. 일정 시간이 지나면 무작위 회전
        if (Time.time >= this.nextTurnTime) {
            this.RotateRandomly();
            this.ScheduleNextTurn();
        }
    }

    private RotateRandomly(): void {
        const angle = Random.RangeFloat(-120, 120);
        this.transform.Rotate(0, angle, 0);
    }

    private RotateBackToCenter(): void {
        const angle = Random.RangeFloat(150, 210);
        this.transform.Rotate(0, angle, 0);
    }

    private ScheduleNextTurn(): void {
        const interval = Random.RangeFloat(2, 4); // 초 단위
        this.nextTurnTime = Time.time + interval;
    }

    private IsWithinBounds(): boolean {
        const pos = this.transform.position;
        return (
            pos.x >= this.centerX - this.boundaryHalfSize &&
            pos.x <= this.centerX + this.boundaryHalfSize &&
            pos.z >= this.centerZ - this.boundaryHalfSize &&
            pos.z <= this.centerZ + this.boundaryHalfSize
        );
    }
} 