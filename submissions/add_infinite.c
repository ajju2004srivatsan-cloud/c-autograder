#include <stdio.h>

/* Intentionally non-halting submission to verify first-pass sandbox timeout. */
int main(void) {
    long long lhs = 0;
    long long rhs = 0;
    if (scanf("%lld %lld", &lhs, &rhs) == 2) {
        while (1) {
            lhs += rhs;
        }
    }
    printf("%lld\n", lhs);
    return 0;
}
